import argparse
import glob
import json
import os
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import ramalama.oci
import ramalama.rag
from ramalama.common import get_accel, perror, run_cmd
from ramalama.config import CONFIG
from ramalama.model import MODEL_TYPES
from ramalama.model_factory import ModelFactory
from ramalama.model_store import GlobalModelStore
from ramalama.shortnames import Shortnames
from ramalama.version import print_version, version

shortnames = Shortnames()


class HelpException(Exception):
    pass


class ArgumentParserWithDefaults(argparse.ArgumentParser):
    def add_argument(self, *args, help=None, default=None, **kwargs):
        if help is not None:
            kwargs['help'] = help
        if default is not None and args[0] != '-h':
            kwargs['default'] = default
            if help is not None and help != "==SUPPRESS==":
                kwargs['help'] += ' (default: {})'.format(default)
        super().add_argument(*args, **kwargs)


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
    parser.add_argument(
        "--container",
        dest="container",
        default=CONFIG["container"],
        action="store_true",
        help="""run RamaLama in the default container.
The RAMALAMA_IN_CONTAINER environment variable modifies default behaviour.""",
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
        "--keep-groups",
        dest="podman_keep_groups",
        default=CONFIG["keep_groups"],
        action="store_true",
        help="""pass `--group-add keep-groups` to podman, if using podman.
Needed to access gpu on some systems, but has security implications.""",
    )
    parser.add_argument(
        "--image",
        default=CONFIG["image"],
        help="OCI container image to run with the specified AI model",
    )
    parser.add_argument(
        "--nocontainer",
        dest="container",
        default=CONFIG["nocontainer"],
        action="store_false",
        help="""do not run RamaLama in the default container.
The RAMALAMA_IN_CONTAINER environment variable modifies default behaviour.""",
    )
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
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument("--quiet", "-q", dest="quiet", action="store_true", help="reduce output.")
    verbosity_group.add_argument(
        "--debug",
        action="store_true",
        help="display debug messages",
    )


def configure_subcommands(parser):
    """Add subcommand parsers to the main argument parser."""
    subparsers = parser.add_subparsers(dest="subcommand")
    subparsers.required = False
    bench_parser(subparsers)
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
    mkdirs(args.store)
    if hasattr(args, "MODEL") and args.subcommand != "rm":
        resolved_model = shortnames.resolve(args.MODEL)
        if resolved_model:
            args.UNRESOLVED_MODEL = args.MODEL
            args.MODEL = resolved_model
    if hasattr(args, "runtime_args"):
        args.runtime_args = shlex.split(args.runtime_args)


def login_parser(subparsers):
    parser = subparsers.add_parser("login", help="login to remote registry")
    parser.add_argument("--authfile", help="path of the authentication file")
    parser.add_argument("-p", "--password", dest="password", help="password for registry")
    parser.add_argument(
        "--password-stdin", dest="passwordstdin", action="store_true", help="take the password for registry from stdin"
    )
    parser.add_argument(
        "--tls-verify",
        dest="tlsverify",
        default=True,
        help="require HTTPS and verify certificates when contacting registries",
    )
    parser.add_argument("--token", dest="token", help="token for registry")
    parser.add_argument("-u", "--username", dest="username", help="username for registry")
    parser.add_argument(
        "REGISTRY", nargs="?", type=str, help="OCI Registry where AI models are stored"
    )  # positional argument
    parser.set_defaults(func=login_cli)


def normalize_registry(registry):
    if not registry or registry == "" or registry.startswith("oci://"):
        return "oci://"

    if registry in ["ollama", "hf" "huggingface"]:
        return registry

    return "oci://" + registry


def login_cli(args):
    registry = normalize_registry(args.REGISTRY)

    model = New(registry, args)
    return model.login(args)


def logout_parser(subparsers):
    parser = subparsers.add_parser("logout", help="logout from remote registry")
    # Do not run in a container
    parser.add_argument("--token", help="token for registry")
    parser.add_argument("REGISTRY", nargs="?", type=str, help="OCI Registry where AI models are stored")
    parser.set_defaults(func=logout_cli)


def logout_cli(args):
    registry = normalize_registry(args.REGISTRY)
    model = New(registry, args)
    return model.logout(args)


def mkdirs(store):
    # List of directories to create
    directories = [
        "models/huggingface",
        "repos/huggingface",
        "models/oci",
        "repos/oci",
        "models/ollama",
        "repos/ollama",
    ]

    # Create each directory
    for directory in directories:
        full_path = os.path.join(store, directory)
        os.makedirs(full_path, exist_ok=True)


def human_duration(d):
    if d < 1:
        return "Less than a second"
    elif d == 1:
        return "1 second"
    elif d < 60:
        return f"{d} seconds"
    elif d < 120:
        return "1 minute"
    elif d < 3600:
        return f"{d // 60} minutes"
    elif d < 7200:
        return "1 hour"
    elif d < 86400:
        return f"{d // 3600} hours"
    elif d < 172800:
        return "1 day"
    elif d < 604800:
        return f"{d // 86400} days"
    elif d < 1209600:
        return "1 week"
    elif d < 2419200:
        return f"{d // 604800} weeks"
    elif d < 4838400:
        return "1 month"
    elif d < 31536000:
        return f"{d // 2419200} months"
    elif d < 63072000:
        return "1 year"
    else:
        return f"{d // 31536000} years"


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
    bench_run_serve_perplexity_args(parser)
    add_network_argument(parser)
    parser.add_argument("MODEL")  # positional argument
    parser.set_defaults(func=bench_cli)


def containers_parser(subparsers):
    parser = subparsers.add_parser("containers", aliases=["ps"], help="list all RamaLama containers")
    parser.add_argument("--format", help="pretty-print containers to JSON or using a Go template")
    parser.add_argument("-n", "--noheading", dest="noheading", action="store_true", help="do not display heading")
    parser.add_argument("--no-trunc", dest="notrunc", action="store_true", help="display the extended information")
    parser.set_defaults(func=list_containers)


def _list_containers(args):
    conman = args.engine
    if conman == "" or conman is None:
        raise ValueError("no container manager (Podman, Docker) found")

    conman_args = [conman, "ps", "-a", "--filter", "label=ai.ramalama"]
    if hasattr(args, "noheading") and args.noheading:
        conman_args += ["--noheading"]

    if hasattr(args, "notrunc") and args.notrunc:
        conman_args += ["--no-trunc"]

    if args.format:
        conman_args += [f"--format={args.format}"]

    try:
        output = run_cmd(conman_args, debug=args.debug).stdout.decode("utf-8").strip()
        if output == "":
            return []
        return output.split("\n")
    except subprocess.CalledProcessError as e:
        perror("ramalama list command requires a running container engine")
        raise (e)


def list_containers(args):
    if len(_list_containers(args)) == 0:
        return
    print("\n".join(_list_containers(args)))


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
        for dirpath, dirnames, filenames in os.walk(path, followlinks=True):
            for file in filenames:
                filepath = os.path.join(dirpath, file)
                if not os.path.islink(filepath):
                    size += os.path.getsize(filepath)
        return size
    return os.path.getsize(path)


def _list_models(args):
    mycwd = os.getcwd()
    if args.use_model_store:
        models = GlobalModelStore(args.store).list_models(engine=args.engine, debug=args.debug)
        ret = []
        local_timezone = datetime.now().astimezone().tzinfo

        for model, files in models.items():
            size_sum = 0
            last_modified = 0.0
            for file in files:
                size_sum += file.size
                if file.modified > last_modified:
                    last_modified = file.modified
            ret.append(
                {
                    "name": model,
                    "modified": datetime.fromtimestamp(last_modified, tz=local_timezone).isoformat(),
                    "size": size_sum,
                }
            )
        return ret
    else:
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

    models.extend(ramalama.oci.list_models(args))

    os.chdir(mycwd)
    return models


def engine_info(args):
    conman = args.engine
    if conman == "":
        raise ValueError("no container manager (Podman, Docker) found")

    conman_args = [conman, "info", "--format", "json"]
    try:
        output = run_cmd(conman_args, debug=args.debug).stdout.decode("utf-8").strip()
        if output == "":
            return []
        return json.loads(output)
    except FileNotFoundError as e:
        return str(e)


def info_cli(args):
    info = {
        "Engine": {
            "Name": args.engine,
        },
        "UseContainer": args.container,
        "Image": args.image,
        "Runtime": args.runtime,
        "Store": args.store,
        "Version": version(),
    }
    if args.engine and len(args.engine) > 0:
        info["Engine"]["Info"] = engine_info(args)

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
    parser.add_argument("MODEL")  # positional argument
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
        "--type",
        default="raw",
        choices=["car", "raw"],
        help="""\
type of OCI Model Image to push.

Model "car" includes base image with the model stored in a /models subdir.
Model "raw" contains the model and a link file model.file to it stored at /.""",
    )
    add_network_argument(parser)
    parser.add_argument("SOURCE")  # positional argument
    parser.add_argument("TARGET")  # positional argument
    parser.set_defaults(func=convert_cli)


def convert_cli(args):
    if not args.container:
        raise ValueError("convert command cannot be run with the --nocontainer option.")

    target = args.TARGET
    source = _get_source(args)

    tgt = shortnames.resolve(target)
    if not tgt:
        tgt = target

    model = ModelFactory(tgt, args).create_oci()
    model.convert(source, args)


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
    parser.add_argument("SOURCE")  # positional argument
    parser.add_argument("TARGET", nargs="?")  # positional argument
    parser.set_defaults(func=push_cli)


def _get_source(args):
    if os.path.exists(args.SOURCE):
        return args.SOURCE

    src = shortnames.resolve(args.SOURCE)
    if not src:
        src = args.SOURCE
    smodel = New(src, args)
    if smodel.type == "OCI":
        raise ValueError("converting from an OCI based image %s is not supported" % src)
    if not smodel.exists(args):
        return smodel.pull(args)
    return smodel.model_path(args)


def push_cli(args):
    if args.TARGET:
        target = args.TARGET
        source = _get_source(args)
    else:
        target = args.SOURCE
        source = args.SOURCE

    tgt = shortnames.resolve(target)
    if not tgt:
        tgt = target

    try:
        model = New(tgt, args)
        model.push(source, args)
    except NotImplementedError as e:
        for mtype in MODEL_TYPES:
            if tgt.startswith(mtype + "://"):
                raise e
        try:
            # attempt to push as a container image
            m = ModelFactory(tgt, args, engine=CONFIG['engine']).create_oci()
            m.push(source, args)
        except Exception:
            raise e


def run_serve_perplexity_args(parser):
    bench_run_serve_perplexity_args(parser)
    parser.add_argument(
        "-c",
        "--ctx-size",
        dest="context",
        default=CONFIG['ctx_size'],
        help="size of the prompt context (0 = loaded from model)",
    )
    parser.add_argument(
        "--runtime-args",
        dest="runtime_args",
        default="",
        type=str,
        help="arguments to add to runtime invocation",
    )


def default_threads():
    if CONFIG["threads"] < 0:
        nproc = os.cpu_count()
        if nproc and nproc > 4:
            return int(nproc / 2)

        return 4

    return CONFIG["threads"]


def add_exec_arguments(parser):
    parser.add_argument(
        "--ngl",
        dest="ngl",
        type=int,
        default=CONFIG["ngl"],
        help="number of layers to offload to the gpu, if available",
    )

    def_threads = default_threads()
    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=def_threads,
        help=f"number of cpu threads to use, the default is {def_threads} on this system, -1 means use this default",
    )
    parser.add_argument("--temp", default=CONFIG['temp'], help="temperature of the response from the AI model")


def bench_run_serve_perplexity_args(parser):
    add_exec_arguments(parser)
    parser.add_argument("--authfile", help="path of the authentication file")
    parser.add_argument(
        "--env",
        dest="env",
        action='append',
        type=str,
        default=CONFIG["env"],
        help="environment variables to add to the running container",
    )
    parser.add_argument(
        "--device", dest="device", action='append', type=str, help="device to leak in to the running container"
    )
    parser.add_argument("-n", "--name", dest="name", help="name of container in which the Model will be run")
    parser.add_argument(
        "--oci-runtime",
        help="override the default OCI runtime used to launch the container",
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
    parser.add_argument("--seed", help="override random seed")
    parser.add_argument(
        "--tls-verify",
        dest="tlsverify",
        default=True,
        help="require HTTPS and verify certificates when contacting registries",
    )


def run_parser(subparsers):
    parser = subparsers.add_parser("run", help="run specified AI Model as a chatbot")
    run_serve_perplexity_args(parser)
    add_network_argument(parser)
    parser.add_argument("--keepalive", type=str, help="duration to keep a model loaded (e.g. 5m)")
    parser.add_argument("--rag", help="RAG vector database or OCI Image to be served with the model")
    parser.add_argument("MODEL")  # positional argument
    parser.add_argument(
        "ARGS", nargs="*", help="overrides the default prompt, and the output is returned without entering the chatbot"
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
        args.generate = ''

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
    run_serve_perplexity_args(parser)
    add_network_argument(parser, dflt=None)
    parser.add_argument("-d", "--detach", action="store_true", dest="detach", help="run the container in detached mode")
    parser.add_argument(
        "--host",
        default=CONFIG['host'],
        help="IP address to listen",
    )
    parser.add_argument(
        "--generate",
        choices=["quadlet", "kube", "quadlet/kube"],
        help="generate specified configuration format for running the AI Model as a service",
    )
    parser.add_argument("-p", "--port", default=CONFIG['port'], help="port for AI Model server to listen on")
    parser.add_argument("--rag", help="RAG vector database or OCI Image to be served with the model")
    parser.add_argument("MODEL")  # positional argument
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
    parser.add_argument("NAME", nargs="?")  # positional argument
    parser.set_defaults(func=stop_container)


def _stop_container(args, name):
    if not name:
        raise ValueError("must specify a container name")
    conman = args.engine
    if conman == "":
        raise ValueError("no container manager (Podman, Docker) found")

    conman_args = [conman, "stop", "-t=0"]
    ignore_stderr = False
    if args.ignore:
        if conman == "podman":
            conman_args += ["--ignore", str(args.ignore)]
        else:
            ignore_stderr = True

    conman_args += [name]
    try:
        run_cmd(conman_args, ignore_stderr=ignore_stderr, debug=args.debug)
    except subprocess.CalledProcessError:
        if args.ignore and conman == "docker":
            return
        else:
            raise


def stop_container(args):
    if not args.all:
        return _stop_container(args, args.NAME)

    if args.NAME:
        raise ValueError("specifying --all and container name, %s, not allowed" % args.NAME)
    args.ignore = True
    args.format = "{{ .Names }}"
    for i in _list_containers(args):
        _stop_container(args, i)


def version_parser(subparsers):
    parser = subparsers.add_parser("version", help="display version of AI Model")
    parser.set_defaults(func=print_version)


def rag_parser(subparsers):
    parser = subparsers.add_parser(
        "rag",
        help="generate and convert retrieval augmented generation (RAG) data from provided documents into an OCI Image",
    )
    add_network_argument(parser, dflt=None)
    parser.add_argument(
        "PATH",
        nargs="*",
        help="""\
Files/Directory containing PDF, DOCX, PPTX, XLSX, HTML, AsciiDoc & Markdown
formatted files to be processed""",
    )
    parser.add_argument("IMAGE", help="OCI Image name to contain processed rag data")
    parser.set_defaults(func=rag_cli)


def rag_cli(args):
    rag = ramalama.rag.Rag(args.IMAGE)
    rag.generate(args)


def rm_parser(subparsers):
    parser = subparsers.add_parser("rm", help="remove AI Model from local storage")
    parser.add_argument("-a", "--all", action="store_true", help="remove all local Models")
    parser.add_argument("--ignore", action="store_true", help="ignore errors when specified Model does not exist")
    parser.add_argument("MODEL", nargs="*")
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

    models = [k['name'] for k in _list_models(args)]
    _rm_model(models, args)


def New(model, args, transport=CONFIG["transport"]):
    return ModelFactory(model, args, transport=transport).create()


def perplexity_parser(subparsers):
    parser = subparsers.add_parser("perplexity", help="calculate perplexity for specified AI Model")
    run_serve_perplexity_args(parser)
    add_network_argument(parser)
    parser.add_argument("MODEL")  # positional argument
    parser.set_defaults(func=perplexity_cli)


def perplexity_cli(args):
    model = New(args.MODEL, args)
    model.perplexity(args)


def inspect_parser(subparsers):
    parser = subparsers.add_parser("inspect", help="inspect an AI Model")
    parser.add_argument("MODEL")  # positional argument
    parser.add_argument("--all", dest="all", action="store_true", help="display all available information of AI Model")
    parser.add_argument("--json", dest="json", action="store_true", help="display AI Model information in JSON format")
    parser.set_defaults(func=inspect_cli)


def inspect_cli(args):
    model = New(args.MODEL, args)
    model.inspect(args)
