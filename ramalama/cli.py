import argparse
import errno
import glob
import json
import os
import shlex
import subprocess
import sys
import urllib
from datetime import datetime, timezone
from pathlib import Path

# if autocomplete doesn't exist, just do nothing, don't break
try:
    import argcomplete

    suppressCompleter = argcomplete.completers.SuppressCompleter
except Exception:
    suppressCompleter = None


import ramalama.oci
import ramalama.rag
from ramalama import engine
from ramalama.common import accel_image, exec_cmd, get_accel, get_cmd_with_wrapper, perror
from ramalama.config import CONFIG
from ramalama.logger import configure_logger, logger
from ramalama.migrate import ModelStoreImport
from ramalama.model import MODEL_TYPES
from ramalama.model_factory import ModelFactory, New
from ramalama.model_store import GlobalModelStore
from ramalama.shortnames import Shortnames
from ramalama.stack import Stack
from ramalama.version import print_version, version

shortnames = Shortnames()


GENERATE_OPTIONS = ["quadlet", "kube", "quadlet/kube"]


class ParsedGenerateInput:

    def __init__(self, gen_type: str, output_dir: str):
        self.gen_type = gen_type
        self.output_dir = output_dir

    def __str__(self):
        return self.gen_type

    def __repr__(self):
        return self.__str__()

    def __eq__(self, value):
        return self.gen_type == value


def parse_generate_option(option: str) -> ParsedGenerateInput:
    # default output directory is where ramalama has been started from
    generate, output_dir = option, "."
    if generate.count(":") == 1:
        generate, output_dir = generate.split(":")
    if output_dir == "":
        output_dir = "."

    return ParsedGenerateInput(generate, output_dir)


def parse_port_option(option: str) -> str:
    port = int(option)
    if port <= 0 or port >= 65535:
        raise ValueError(f"Invalid port '{port}'")
    return str(port)


class OverrideDefaultAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
        setattr(namespace, self.dest + '_override', True)


class HelpException(Exception):
    pass


def local_env(**kwargs):
    return os.environ


def local_models(prefix, parsed_args, **kwargs):
    return [model['name'] for model in _list_models(parsed_args)]


def local_containers(prefix, parsed_args, **kwargs):
    parsed_args.format = '{{.Names}}'
    return engine.containers(parsed_args)


def local_images(prefix, parsed_args, **kwargs):
    parsed_args.format = "{{.Repository}}:{{.Tag}}"
    return engine.images(parsed_args)


class ArgumentParserWithDefaults(argparse.ArgumentParser):
    def add_argument(self, *args, help=None, default=None, completer=None, **kwargs):
        if help is not None:
            kwargs['help'] = help
        if default is not None and args[0] != '-h':
            kwargs['default'] = default
            if help is not None and help != "==SUPPRESS==":
                kwargs['help'] += f' (default: {default})'
        action = super().add_argument(*args, **kwargs)
        if completer is not None:
            action.completer = completer
        return action


def init_cli():
    """Initialize the RamaLama CLI and parse command line arguments."""
    description = get_description()
    parser = create_argument_parser(description)
    configure_subcommands(parser)
    args = parse_arguments(parser)
    post_parse_setup(args)
    return parser, args


def get_description():
    """Return the description of the RamaLama tool."""
    return """\
RamaLama tool facilitates local management and serving of AI Models.

On first run RamaLama inspects your system for GPU support, falling back to CPU support if no GPUs are present.

RamaLama uses container engines like Podman or Docker to pull the appropriate OCI image with all of the software \
necessary to run an AI Model for your systems setup.

Running in containers eliminates the need for users to configure the host system for AI. After the initialization, \
RamaLama runs the AI Models within a container based on the OCI image.

RamaLama then pulls AI Models from model registries. Starting a chatbot or a rest API service from a simple single \
command. Models are treated similarly to how Podman and Docker treat container images.

When both Podman and Docker are installed, RamaLama defaults to Podman. The `RAMALAMA_CONTAINER_ENGINE=docker` \
environment variable can override this behaviour. When neither are installed, RamaLama will attempt to run the model \
with software on the local system.
"""


def create_argument_parser(description):
    """Create and configure the argument parser for the CLI."""
    parser = ArgumentParserWithDefaults(
        prog="ramalama",
        description=description,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    configure_arguments(parser)
    return parser


def configure_arguments(parser):
    """Configure the command-line arguments for the parser."""
    verbosity_group = parser.add_mutually_exclusive_group()
    parser.add_argument(
        "--container",
        dest="container",
        default=CONFIG["container"],
        action="store_true",
        help="""run RamaLama in the default container.
The RAMALAMA_IN_CONTAINER environment variable modifies default behaviour.""",
    )
    verbosity_group.add_argument(
        "--debug",
        action="store_true",
        help="display debug messages",
    )
    parser.add_argument(
        "--dryrun",
        "--dry-run",
        dest="dryrun",
        action="store_true",
        help="show container runtime command without executing it",
    )
    parser.add_argument(
        "--engine",
        dest="engine",
        default=CONFIG["engine"],
        help="""run RamaLama using the specified container engine.
The RAMALAMA_CONTAINER_ENGINE environment variable modifies default behaviour.""",
    )
    parser.add_argument(
        "--image",
        default=accel_image(CONFIG, None),
        help="OCI container image to run with the specified AI model",
        action=OverrideDefaultAction,
        completer=local_images,
    )
    parser.add_argument(
        "--keep-groups",
        dest="podman_keep_groups",
        default=CONFIG["keep_groups"],
        action="store_true",
        help="""pass `--group-add keep-groups` to podman, if using podman.
Needed to access gpu on some systems, but has security implications.""",
    )
    parser.add_argument(
        "--nocontainer",
        dest="container",
        default=CONFIG["nocontainer"],
        action="store_false",
        help="""do not run RamaLama in the default container.
The RAMALAMA_IN_CONTAINER environment variable modifies default behaviour.""",
    )
    verbosity_group.add_argument("--quiet", "-q", dest="quiet", action="store_true", help="reduce output.")
    parser.add_argument(
        "--runtime",
        default=CONFIG["runtime"],
        choices=["llama.cpp", "vllm"],
        help="specify the runtime to use; valid options are 'llama.cpp' and 'vllm'",
    )
    parser.add_argument(
        "--store",
        default=CONFIG["store"],
        help="store AI Models in the specified directory",
    )
    parser.add_argument(
        "--use-model-store",
        dest="use_model_store",
        default=CONFIG["use_model_store"],
        action="store_true",
        help="use the model store feature",
    )


def configure_subcommands(parser):
    """Add subcommand parsers to the main argument parser."""
    subparsers = parser.add_subparsers(dest="subcommand")
    subparsers.required = False
    bench_parser(subparsers)
    client_parser(subparsers)
    containers_parser(subparsers)
    convert_parser(subparsers)
    help_parser(subparsers)
    info_parser(subparsers)
    inspect_parser(subparsers)
    list_parser(subparsers)
    login_parser(subparsers)
    logout_parser(subparsers)
    perplexity_parser(subparsers)
    pull_parser(subparsers)
    push_parser(subparsers)
    rag_parser(subparsers)
    rm_parser(subparsers)
    run_parser(subparsers)
    serve_parser(subparsers)
    stop_parser(subparsers)
    version_parser(subparsers)


def parse_arguments(parser):
    """Parse command line arguments."""
    return parser.parse_args()


def post_parse_setup(args):
    """Perform additional setup after parsing arguments."""
    if hasattr(args, "MODEL") and args.subcommand != "rm":
        resolved_model = shortnames.resolve(args.MODEL)
        if resolved_model:
            args.UNRESOLVED_MODEL = args.MODEL
            args.MODEL = resolved_model
    if hasattr(args, "runtime_args"):
        args.runtime_args = shlex.split(args.runtime_args)

    configure_logger("DEBUG" if args.debug else "WARNING")


def login_parser(subparsers):
    parser = subparsers.add_parser("login", help="login to remote registry")
    parser.add_argument("--authfile", help="path of the authentication file")
    parser.add_argument("-p", "--password", dest="password", help="password for registry", completer=suppressCompleter)
    parser.add_argument(
        "--password-stdin", dest="passwordstdin", action="store_true", help="take the password for registry from stdin"
    )
    parser.add_argument(
        "--tls-verify",
        dest="tlsverify",
        default=True,
        help="require HTTPS and verify certificates when contacting registries",
    )
    parser.add_argument("--token", dest="token", help="token for registry", completer=suppressCompleter)
    parser.add_argument("-u", "--username", dest="username", help="username for registry", completer=suppressCompleter)
    parser.add_argument(
        "REGISTRY", nargs="?", type=str, help="OCI Registry where AI models are stored", completer=suppressCompleter
    )
    parser.set_defaults(func=login_cli)


def normalize_registry(registry):
    # Determine the registry to use. Check the value of `RAMALAMA_TRANSPORT` env var if no `registry` argument is set.
    registry = registry or os.getenv("RAMALAMA_TRANSPORT") or CONFIG['transport']

    if not registry or registry == "" or registry.startswith("oci://"):
        return "oci://"

    if registry in ["ollama", "hf", "huggingface", "ms", "modelscope"]:
        return registry

    return "oci://" + registry


def login_cli(args):
    registry = normalize_registry(args.REGISTRY)

    model = New(registry, args)
    return model.login(args)


def logout_parser(subparsers):
    parser = subparsers.add_parser("logout", help="logout from remote registry")
    # Do not run in a container
    parser.add_argument("--token", help="token for registry", completer=suppressCompleter)
    parser.add_argument(
        "REGISTRY", nargs="?", type=str, help="OCI Registry where AI models are stored", completer=suppressCompleter
    )
    parser.set_defaults(func=logout_cli)


def logout_cli(args):
    registry = normalize_registry(args.REGISTRY)
    model = New(registry, args)
    return model.logout(args)


def human_duration(d):
    if d < 1:
        return "Less than a second"
    if d == 1:
        return "1 second"
    if d < 60:
        return f"{d} seconds"
    if d < 120:
        return "1 minute"
    if d < 3600:
        return f"{d // 60} minutes"
    if d < 7200:
        return "1 hour"
    if d < 86400:
        return f"{d // 3600} hours"
    if d < 172800:
        return "1 day"
    if d < 604800:
        return f"{d // 86400} days"
    if d < 1209600:
        return "1 week"
    if d < 2419200:
        return f"{d // 604800} weeks"
    if d < 4838400:
        return "1 month"
    if d < 31536000:
        return f"{d // 2419200} months"
    return "1 year" if d < 63072000 else f"{d // 31536000} years"


def list_files_by_modification(args):
    paths = Path().rglob("*")
    models = []
    for path in paths:
        if str(path).startswith("file/"):
            if not os.path.exists(str(path)):
                path = str(path).replace("file/", "file:///")
                perror(f"{path} does not exist")
                continue
        if os.path.exists(path):
            models.append(path)
        else:
            print(f"Broken symlink found in: {args.store}/models/{path} \nAttempting removal")
            New(str(path).replace("/", "://", 1), args).remove(args)

    return sorted(models, key=lambda p: os.path.getmtime(p), reverse=True)


def bench_cli(args):
    model = New(args.MODEL, args)
    model.bench(args)


def add_network_argument(parser, dflt="none"):
    # Disable network access by default, and give the option to pass any supported network mode into
    # podman if needed:
    # https://docs.podman.io/en/latest/markdown/podman-run.1.html#network-mode-net
    # https://docs.podman.io/en/latest/markdown/podman-build.1.html#network-mode-net
    if dflt:
        parser.add_argument(
            "--network",
            "--net",
            type=str,
            default=dflt,
            help="set the network mode for the container",
        )
    else:
        parser.add_argument(
            "--network",
            "--net",
            type=str,
            help="set the network mode for the container",
        )


def bench_parser(subparsers):
    parser = subparsers.add_parser("bench", aliases=["benchmark"], help="benchmark specified AI Model")
    runtime_options(parser, "bench")
    parser.add_argument("MODEL", completer=local_models)  # positional argument
    parser.set_defaults(func=bench_cli)


def containers_parser(subparsers):
    parser = subparsers.add_parser("containers", aliases=["ps"], help="list all RamaLama containers")
    parser.add_argument(
        "--format", help="pretty-print containers to JSON or using a Go template", completer=suppressCompleter
    )
    parser.add_argument("-n", "--noheading", dest="noheading", action="store_true", help="do not display heading")
    parser.add_argument("--no-trunc", dest="notrunc", action="store_true", help="display the extended information")
    parser.set_defaults(func=list_containers)


def list_containers(args):
    containers = engine.containers(args)
    if len(containers) == 0:
        return
    print("\n".join(containers))


def info_parser(subparsers):
    parser = subparsers.add_parser("info", help="display information pertaining to setup of RamaLama.")
    parser.set_defaults(func=info_cli)


def list_parser(subparsers):
    parser = subparsers.add_parser("list", aliases=["ls"], help="list all downloaded AI Models")
    parser.add_argument("--json", dest="json", action="store_true", help="print using json")
    parser.add_argument("-n", "--noheading", dest="noheading", action="store_true", help="do not display heading")
    parser.set_defaults(func=list_cli)


def human_readable_size(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            size = round(size, 2)
            return f"{size} {unit}"

        size /= 1024

    return f"{size} PB"


def get_size(path):
    if os.path.isdir(path):
        size = 0
        for dirpath, _, filenames in os.walk(path, followlinks=True):
            for file in filenames:
                filepath = os.path.join(dirpath, file)
                if not os.path.islink(filepath):
                    size += os.path.getsize(filepath)
        return size
    return os.path.getsize(path)


def _list_models(args):
    mycwd = os.getcwd()
    if args.use_model_store:
        models = GlobalModelStore(args.store).list_models(engine=args.engine, show_container=args.container)
        ret = []
        local_timezone = datetime.now().astimezone().tzinfo

        for model, files in models.items():
            size_sum = 0
            last_modified = 0.0
            for file in files:
                size_sum += file.size
                last_modified = max(file.modified, last_modified)
            ret.append(
                {
                    "name": model,
                    "modified": datetime.fromtimestamp(last_modified, tz=local_timezone).isoformat(),
                    "size": size_sum,
                }
            )
        return ret
    os.chdir(f"{args.store}/models/")
    models = []

    # Collect model data
    for path in list_files_by_modification(args):
        if path.is_symlink():
            if str(path).startswith("file/"):
                name = str(path).replace("/", ":///", 1)
            else:
                name = str(path).replace("/", "://", 1)
            file_epoch = path.lstat().st_mtime
            # convert to iso format
            modified = datetime.fromtimestamp(file_epoch, tz=timezone.utc).isoformat()
            size = get_size(path)

            # Store data for later use
            models.append({"name": name, "modified": modified, "size": size})

    if args.container:
        models.extend(ramalama.oci.list_models(args))

    os.chdir(mycwd)
    return models


def info_cli(args):
    info = {
        "Engine": {
            "Name": args.engine,
        },
        "Image": args.image,
        "Runtime": args.runtime,
        "Store": args.store,
        "UseContainer": args.container,
        "Version": version(),
    }
    info["Shortnames"] = {
        "Files": shortnames.paths,
        "Names": shortnames.shortnames,
    }
    if args.engine and len(args.engine) > 0:
        info["Engine"]["Info"] = engine.info(args)

    info["Accelerator"] = get_accel()
    print(json.dumps(info, sort_keys=True, indent=4))


def list_cli(args):
    models = _list_models(args)

    # If JSON output is requested
    if args.json:
        print(json.dumps(models))
        return

    # Calculate maximum width for each column
    name_width = len("NAME")
    modified_width = len("MODIFIED")
    size_width = len("SIZE")
    for model in sorted(models, key=lambda d: d['name']):
        try:
            delta = int(datetime.now(timezone.utc).timestamp() - datetime.fromisoformat(model["modified"]).timestamp())
            modified = human_duration(delta) + " ago"
            model["modified"] = modified
        except TypeError:
            pass
        # update the size to be human readable
        model["size"] = human_readable_size(model["size"])
        name_width = max(name_width, len(model["name"]))
        modified_width = max(modified_width, len(model["modified"]))
        size_width = max(size_width, len(model["size"]))

    if not args.quiet and not args.noheading and not args.json:
        print(f"{'NAME':<{name_width}} {'MODIFIED':<{modified_width}} {'SIZE':<{size_width}}")

    for model in models:
        if args.quiet:
            print(model["name"])
        else:
            modified = model['modified']
            print(f"{model['name']:<{name_width}} {modified:<{modified_width}} {model['size'].upper():<{size_width}}")


def help_parser(subparsers):
    parser = subparsers.add_parser("help")
    # Do not run in a container
    parser.set_defaults(func=help_cli)


def help_cli(args):
    raise HelpException()


def pull_parser(subparsers):
    parser = subparsers.add_parser("pull", help="pull AI Model from Model registry to local storage")
    parser.add_argument("--authfile", help="path of the authentication file")
    parser.add_argument(
        "--tls-verify",
        dest="tlsverify",
        default=True,
        help="require HTTPS and verify certificates when contacting registries",
    )
    parser.add_argument("MODEL", completer=suppressCompleter)  # positional argument
    parser.set_defaults(func=pull_cli)


def pull_cli(args):
    model = New(args.MODEL, args)
    matching_files = glob.glob(f"{args.store}/models/*/{model}")
    if matching_files:
        return matching_files[0]

    return model.pull(args)


def convert_parser(subparsers):
    parser = subparsers.add_parser(
        "convert",
        help="convert AI Model from local storage to OCI Image",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--carimage",
        default=CONFIG['carimage'],
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--gguf",
        choices=[
            "Q2_K",
            "Q3_K_S",
            "Q3_K_M",
            "Q3_K_L",
            "Q4_0",
            "Q4_K_S",
            "Q4_K_M",
            "Q5_0",
            "Q5_K_S",
            "Q5_K_M",
            "Q6_K",
            "Q8_0",
        ],
        help="GGUF quantization format",
    )
    add_network_argument(parser)
    parser.add_argument(
        "--type",
        default="raw",
        choices=["car", "raw"],
        help="""\
type of OCI Model Image to push.

Model "car" includes base image with the model stored in a /models subdir.
Model "raw" contains the model and a link file model.file to it stored at /.""",
    )
    parser.add_argument("SOURCE")  # positional argument
    parser.add_argument("TARGET")  # positional argument
    parser.set_defaults(func=convert_cli)


def convert_cli(args):
    if not args.container:
        raise ValueError("convert command cannot be run with the --nocontainer option.")

    target = args.TARGET
    source_model = _get_source_model(args)

    tgt = shortnames.resolve(target)
    if not tgt:
        tgt = target

    model = ModelFactory(tgt, args).create_oci()
    model.convert(source_model, args)


def push_parser(subparsers):
    parser = subparsers.add_parser(
        "push",
        help="push AI Model from local storage to remote registry",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--authfile", help="path of the authentication file")
    parser.add_argument(
        "--carimage",
        default=CONFIG['carimage'],
        help=argparse.SUPPRESS,
    )
    add_network_argument(parser)
    parser.add_argument(
        "--type",
        default="raw",
        choices=["car", "raw"],
        help="""\
type of OCI Model Image to push.

Model "car" includes base image with the model stored in a /models subdir.
Model "raw" contains the model and a link file model.file to it stored at /.""",
    )
    parser.add_argument(
        "--tls-verify",
        dest="tlsverify",
        default=True,
        help="require HTTPS and verify certificates when contacting registries",
    )
    parser.add_argument("SOURCE", completer=local_models)  # positional argument
    parser.add_argument("TARGET", nargs="?", completer=suppressCompleter)  # positional argument
    parser.set_defaults(func=push_cli)


def _get_source_model(args):
    src = shortnames.resolve(args.SOURCE)
    if not src:
        src = args.SOURCE
    smodel = New(src, args)
    if smodel.type == "OCI":
        raise ValueError(f"converting from an OCI based image {src} is not supported")
    if not smodel.exists(args):
        smodel.pull(args)
    return smodel


def push_cli(args):
    source_model = _get_source_model(args)
    target = args.SOURCE
    if args.TARGET:
        target = shortnames.resolve(args.TARGET)
        if not target:
            target = args.TARGET
    target_model = New(target, args)

    try:
        target_model.push(source_model, args)
    except NotImplementedError as e:
        for mtype in MODEL_TYPES:
            if target.startswith(mtype + "://"):
                raise e
        try:
            # attempt to push as a container image
            m = ModelFactory(target, args).create_oci()
            m.push(source_model, args)
        except Exception as e1:
            logger.debug(e1)
            raise e


def runtime_options(parser, command):
    if command in ["run", "serve"]:
        parser.add_argument(
            "--api",
            default=CONFIG["api"],
            choices=["llama-stack", "none"],
            help="unified API layer for for Inference, RAG, Agents, Tools, Safety, Evals, and Telemetry.",
        )
    parser.add_argument("--authfile", help="path of the authentication file")
    if command in ["run", "perplexity", "serve"]:
        parser.add_argument(
            "-c",
            "--ctx-size",
            dest="context",
            default=CONFIG['ctx_size'],
            help="size of the prompt context (0 = loaded from model)",
            completer=suppressCompleter,
        )
    if command == "serve":
        parser.add_argument(
            "-d", "--detach", action="store_true", dest="detach", help="run the container in detached mode"
        )
    parser.add_argument(
        "--device", dest="device", action='append', type=str, help="device to leak in to the running container"
    )
    parser.add_argument(
        "--env",
        dest="env",
        action='append',
        type=str,
        default=CONFIG["env"],
        help="environment variables to add to the running container",
        completer=local_env,
    )
    if command == "serve":
        parser.add_argument(
            "--generate",
            type=parse_generate_option,
            choices=GENERATE_OPTIONS,
            help="generate specified configuration format for running the AI Model as a service",
        )
        parser.add_argument(
            "--host",
            default=CONFIG['host'],
            help="IP address to listen",
            completer=suppressCompleter,
        )
    if command == "run":
        parser.add_argument(
            "--keepalive", type=str, help="duration to keep a model loaded (e.g. 5m)", completer=suppressCompleter
        )
    if command == "serve":
        parser.add_argument("--model-draft", help="Draft model", completer=local_models)

    parser.add_argument(
        "-n",
        "--name",
        dest="name",
        help="name of container in which the Model will be run",
        completer=suppressCompleter,
    )
    if command == "serve":
        add_network_argument(parser, dflt=None)
    else:
        add_network_argument(parser)

    parser.add_argument(
        "--ngl",
        dest="ngl",
        type=int,
        default=CONFIG["ngl"],
        help="number of layers to offload to the gpu, if available",
        completer=suppressCompleter,
    )
    parser.add_argument(
        "--oci-runtime",
        help="override the default OCI runtime used to launch the container",
        completer=suppressCompleter,
    )
    if command == "serve":
        parser.add_argument(
            "-p",
            "--port",
            type=parse_port_option,
            default=CONFIG['port'],
            help="port for AI Model server to listen on",
            completer=suppressCompleter,
        )
    parser.add_argument(
        "--privileged", dest="privileged", action="store_true", help="give extended privileges to container"
    )
    parser.add_argument(
        "--pull",
        dest="pull",
        type=str,
        default=CONFIG['pull'],
        choices=["always", "missing", "never", "newer"],
        help='pull image policy',
    )
    if command in ["run", "serve"]:
        parser.add_argument(
            "--rag", help="RAG vector database or OCI Image to be served with the model", completer=local_models
        )
    if command in ["perplexity", "run", "serve"]:
        parser.add_argument(
            "--runtime-args",
            dest="runtime_args",
            default="",
            type=str,
            help="arguments to add to runtime invocation",
            completer=suppressCompleter,
        )
    parser.add_argument("--seed", help="override random seed", completer=suppressCompleter)
    parser.add_argument(
        "--temp",
        default=CONFIG['temp'],
        help="temperature of the response from the AI model",
        completer=suppressCompleter,
    )
    def_threads = default_threads()
    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=def_threads,
        help=f"number of cpu threads to use, the default is {def_threads} on this system, -1 means use this default",
        completer=suppressCompleter,
    )
    parser.add_argument(
        "--tls-verify",
        dest="tlsverify",
        default=True,
        help="require HTTPS and verify certificates when contacting registries",
    )
    if command == "serve":
        parser.add_argument(
            "--webui",
            dest="webui",
            choices=["on", "off"],
            default="on",
            help="enable or disable the web UI (default: on)",
        )


def default_threads():
    if CONFIG["threads"] < 0:
        nproc = os.cpu_count()
        if nproc and nproc > 4:
            return int(nproc / 2)

        return 4

    return CONFIG["threads"]


def run_parser(subparsers):
    parser = subparsers.add_parser("run", help="run specified AI Model as a chatbot")
    runtime_options(parser, "run")
    parser.add_argument("MODEL", completer=local_models)  # positional argument
    parser.add_argument(
        "ARGS",
        nargs="*",
        help="overrides the default prompt, and the output is returned without entering the chatbot",
        completer=suppressCompleter,
    )
    parser._actions.sort(key=lambda x: x.option_strings)
    parser.set_defaults(func=run_cli)


def run_cli(args):
    if args.rag:
        _get_rag(args)
        # Passing default args for serve (added network bridge for internet access)
        args.port = CONFIG['port']
        args.host = CONFIG['host']
        args.network = 'bridge'
        args.generate = ParsedGenerateInput("", "")

    try:
        model = New(args.MODEL, args)
        model.serve(args, quiet=True) if args.rag else model.run(args)

    except KeyError as e:
        try:
            args.quiet = True
            model = ModelFactory(args.MODEL, args, ignore_stderr=True).create_oci()
            model.serve(args) if args.rag else model.run(args)
        except Exception:
            raise e


def serve_parser(subparsers):
    parser = subparsers.add_parser("serve", help="serve REST API on specified AI Model")
    runtime_options(parser, "serve")
    parser.add_argument("MODEL", completer=local_models)  # positional argument
    parser.set_defaults(func=serve_cli)


def _get_rag(args):
    if os.path.exists(args.rag):
        return
    model = New(args.rag, args=args, transport="oci")
    if not model.exists(args):
        model.pull(args)


def serve_cli(args):
    if not args.container:
        args.detach = False

    if args.rag:
        _get_rag(args)

    if args.api == "llama-stack":
        if not args.container:
            raise ValueError("ramalama serve --api llama-stack command cannot be run with the --nocontainer option.")

        stack = Stack(args)
        return stack.serve()

    try:
        model = New(args.MODEL, args)
        model.serve(args)
    except KeyError as e:
        try:
            args.quiet = True
            model = ModelFactory(args.MODEL, args, ignore_stderr=True).create_oci()
            model.serve(args)
        except Exception:
            raise e


def stop_parser(subparsers):
    parser = subparsers.add_parser("stop", help="stop named container that is running AI Model")
    parser.add_argument("-a", "--all", action="store_true", help="stop all RamaLama containers")
    parser.add_argument(
        "--ignore", action="store_true", help="ignore errors when specified RamaLama container is missing"
    )
    parser.add_argument("NAME", nargs="?", completer=local_containers)
    parser.set_defaults(func=stop_container)


def stop_container(args):
    if not args.all:
        engine.stop_container(args, args.NAME)
        return

    if args.NAME:
        raise ValueError(f"specifying --all and container name, {args.NAME}, not allowed")
    args.ignore = True
    args.format = "{{ .Names }}"
    for i in engine.containers(args):
        engine.stop_container(args, i)


def version_parser(subparsers):
    parser = subparsers.add_parser("version", help="display version of RamaLama")
    parser.set_defaults(func=print_version)


def client_parser(subparsers):
    """Add parser for client command"""
    parser = subparsers.add_parser("client", help="interact with an OpenAI endpoint")
    parser.add_argument("HOST", help="host to connect to", completer=suppressCompleter)  # positional argument
    parser.add_argument(
        "ARGS",
        nargs="*",
        help="overrides the default prompt, and the output is returned without entering the chatbot",
        completer=suppressCompleter,
    )
    parser.set_defaults(func=client_cli)


def rag_parser(subparsers):
    parser = subparsers.add_parser(
        "rag",
        help="generate and convert retrieval augmented generation (RAG) data from provided documents into an OCI Image",
    )
    parser.add_argument(
        "--env",
        dest="env",
        action='append',
        type=str,
        default=CONFIG["env"],
        help="environment variables to add to the running RAG container",
        completer=local_env,
    )
    add_network_argument(parser, dflt=None)
    parser.add_argument(
        "--pull",
        dest="pull",
        type=str,
        default=CONFIG['pull'],
        choices=["always", "missing", "never", "newer"],
        help='pull image policy',
    )
    parser.add_argument(
        "PATH",
        nargs="*",
        help="""\
Files/Directory containing PDF, DOCX, PPTX, XLSX, HTML, AsciiDoc & Markdown
formatted files to be processed""",
    )
    parser.add_argument("IMAGE", help="OCI Image name to contain processed rag data", completer=suppressCompleter)
    parser.add_argument(
        "--ocr",
        dest="ocr",
        default=CONFIG["ocr"],
        action="store_true",
        help="Enable embedded image text extraction from PDF (Increases RAM Usage significantly)",
    )
    parser.set_defaults(func=rag_cli)


def rag_cli(args):
    rag = ramalama.rag.Rag(args.IMAGE)
    rag.generate(args)


def rm_parser(subparsers):
    parser = subparsers.add_parser("rm", help="remove AI Model from local storage")
    parser.add_argument("-a", "--all", action="store_true", help="remove all local Models")
    parser.add_argument("--ignore", action="store_true", help="ignore errors when specified Model does not exist")
    parser.add_argument("MODEL", nargs="*", completer=local_models)  # positional argument
    parser.set_defaults(func=rm_cli)


def _rm_model(models, args):
    for model in models:
        resolved_model = shortnames.resolve(model)
        if resolved_model:
            model = resolved_model

        try:
            m = New(model, args)
            m.remove(args)
        except KeyError as e:
            for prefix in MODEL_TYPES:
                if model.startswith(prefix + "://"):
                    if not args.ignore:
                        raise e
            try:
                # attempt to remove as a container image
                m = ModelFactory(model, args, ignore_stderr=True).create_oci()
                m.remove(args)
                return
            except Exception:
                pass
            if not args.ignore:
                raise e


def rm_cli(args):
    if not args.all:
        if len(args.MODEL) == 0:
            raise IndexError("one MODEL or --all must be specified")

        return _rm_model(args.MODEL, args)

    if len(args.MODEL) > 0:
        raise IndexError("can not specify --all as well MODEL")

    models = GlobalModelStore(args.store).list_models(engine=args.engine, show_container=args.container)

    return _rm_model([model for model in models.keys()], args)


def client_cli(args):
    """Handle client command execution"""
    client_args = ["ramalama-client-core", "-c", "2048", "--temp", "0.8", args.HOST] + args.ARGS
    client_args[0] = get_cmd_with_wrapper(client_args[0])
    exec_cmd(client_args)


def perplexity_parser(subparsers):
    parser = subparsers.add_parser("perplexity", help="calculate perplexity for specified AI Model")
    runtime_options(parser, "perplexity")
    parser.add_argument("MODEL", completer=local_models)  # positional argument
    parser.set_defaults(func=perplexity_cli)


def perplexity_cli(args):
    model = New(args.MODEL, args)
    model.perplexity(args)


def inspect_parser(subparsers):
    parser = subparsers.add_parser("inspect", help="inspect an AI Model")
    parser.add_argument("--all", dest="all", action="store_true", help="display all available information of AI Model")
    parser.add_argument("--json", dest="json", action="store_true", help="display AI Model information in JSON format")
    parser.add_argument("MODEL", completer=local_models)  # positional argument
    parser.set_defaults(func=inspect_cli)


def inspect_cli(args):
    args.pull = "never"
    model = New(args.MODEL, args)
    model.inspect(args)


def main():
    parser, args = init_cli()

    try:
        import argcomplete

        argcomplete.autocomplete(parser)
    except Exception:
        pass

    try:
        ModelStoreImport(args.store).import_all()
    except Exception as ex:
        perror(f"Error: Failed to import models to new store: {ex}")

    def eprint(e, exit_code):
        perror("Error: " + str(e).strip("'\""))
        sys.exit(exit_code)

    try:
        args.func(args)
    except urllib.error.HTTPError as e:
        eprint(f"pulling {e.geturl()} failed: {e}", errno.EINVAL)
    except HelpException:
        parser.print_help()
    except AttributeError as e:
        parser.print_usage()
        perror("ramalama: requires a subcommand")
        if getattr(args, "debug", False):
            raise e
    except IndexError as e:
        eprint(e, errno.EINVAL)
    except KeyError as e:
        eprint(e, 1)
    except NotImplementedError as e:
        eprint(e, errno.ENOTSUP)
    except subprocess.CalledProcessError as e:
        eprint(e, e.returncode)
    except KeyboardInterrupt:
        sys.exit(0)
    except ConnectionError as e:
        eprint(e, errno.EINVAL)
    except ValueError as e:
        eprint(e, errno.EINVAL)
    except IOError as e:
        eprint(e, errno.EIO)
