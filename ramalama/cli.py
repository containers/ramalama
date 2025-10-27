import argparse
import copy
import errno
import json
import os
import shlex
import subprocess
import sys
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import get_args
from urllib.parse import urlparse

# if autocomplete doesn't exist, just do nothing, don't break
try:
    import argcomplete

    suppressCompleter: type[argcomplete.completers.SuppressCompleter] | None = argcomplete.completers.SuppressCompleter
except Exception:
    suppressCompleter = None


import ramalama.chat as chat
from ramalama import engine
from ramalama.chat import default_prefix
from ramalama.cli_arg_normalization import normalize_pull_arg
from ramalama.command.factory import assemble_command
from ramalama.common import accel_image, get_accel, perror
from ramalama.config import (
    COLOR_OPTIONS,
    CONFIG,
    GGUF_QUANTIZATION_MODES,
    SUPPORTED_ENGINES,
    SUPPORTED_RUNTIMES,
    coerce_to_bool,
    get_inference_schema_files,
    get_inference_spec_files,
    load_file_config,
)
from ramalama.endian import EndianMismatchError
from ramalama.logger import configure_logger, logger
from ramalama.model_inspect.error import ParseError
from ramalama.model_store.global_store import GlobalModelStore
from ramalama.rag import INPUT_DIR, Rag, RagTransport, rag_image
from ramalama.shortnames import Shortnames
from ramalama.stack import Stack
from ramalama.transports.base import (
    MODEL_TYPES,
    NoGGUFModelFileFound,
    NoRefFileFound,
    SafetensorModelNotSupported,
    compute_serving_port,
    trim_model_name,
)
from ramalama.transports.transport_factory import New, TransportFactory
from ramalama.version import print_version, version

shortnames = Shortnames()

GENERATE_OPTIONS = ["quadlet", "kube", "quadlet/kube", "compose"]


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


class CoerceToBool(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, coerce_to_bool(values))


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


def available_metadata(prefix, parsed_args, **kwargs):
    if parsed_args.MODEL:
        # shotnames resolution has not been applied for auto-completion
        # Therefore it needs to be done explicitly here in order to support it
        resolved_model = shortnames.resolve(parsed_args.MODEL)
        if not resolved_model:
            resolved_model = parsed_args.MODEL

        metadata = New(resolved_model, parsed_args).inspect_metadata()
        return [field for field in metadata.keys() if field.startswith(parsed_args.get)]
    return []


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


def get_parser():
    description = get_description()
    parser = create_argument_parser(description)
    configure_subcommands(parser)
    return parser


def init_cli():
    """Initialize the RamaLama CLI and parse command line arguments."""
    # Need to know if we're running with --dryrun or --generate before adding the subcommands,
    # otherwise calls to accel_image() when setting option defaults will cause unnecessary image pulls.
    if any(arg in ("--dryrun", "--dry-run", "--generate") or arg.startswith("--generate=") for arg in sys.argv[1:]):
        CONFIG.dryrun = True
    parser = get_parser()
    args = parse_arguments(parser)
    post_parse_setup(args)
    return parser, args


def parse_args_from_cmd(cmd: list[str]) -> argparse.Namespace:
    """Parse arguments based on a command string"""
    # Need to know if we're running with --dryrun or --generate before adding the subcommands,
    # otherwise calls to accel_image() when setting option defaults will cause unnecessary image pulls.
    if any(arg in ("--dryrun", "--dry-run", "--generate") or arg.startswith("--generate=") for arg in sys.argv[1:]):
        CONFIG.dryrun = True
    parser = get_parser()
    args = parser.parse_args(cmd)
    post_parse_setup(args)
    return args


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


def abspath(astring) -> str:
    return os.path.abspath(astring)


def create_argument_parser(description: str):
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
        default=CONFIG.container,
        action="store_true",
        help=argparse.SUPPRESS,
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
        default=CONFIG.engine,
        choices=get_args(SUPPORTED_ENGINES),
        help="""run RamaLama using the specified container engine.
The RAMALAMA_CONTAINER_ENGINE environment variable modifies default behaviour.""",
    )
    parser.add_argument(
        "--nocontainer",
        dest="container",
        default=not CONFIG.container,
        action="store_false",
        help="""do not run RamaLama in the default container.
The RAMALAMA_IN_CONTAINER environment variable modifies default behaviour.""",
    )
    verbosity_group.add_argument("--quiet", "-q", dest="quiet", action="store_true", help="reduce output.")
    parser.add_argument(
        "--runtime",
        default=CONFIG.runtime,
        choices=get_args(SUPPORTED_RUNTIMES),
        help="specify the runtime to use; valid options are 'llama.cpp', 'vllm', and 'mlx'",
    )
    parser.add_argument(
        "--store",
        default=CONFIG.store,
        type=abspath,
        help="store AI Models in the specified directory",
    )
    parser.add_argument(
        "--noout",
        help=argparse.SUPPRESS,
    )


def configure_subcommands(parser):
    """Add subcommand parsers to the main argument parser."""
    subparsers = parser.add_subparsers(dest="subcommand")
    subparsers.required = False
    bench_parser(subparsers)
    chat_parser(subparsers)
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
    daemon_parser(subparsers)


def parse_arguments(parser):
    """Parse command line arguments."""
    return parser.parse_args()


def post_parse_setup(args):
    """Perform additional setup after parsing arguments."""
    if getattr(args, "MODEL", None):
        if args.subcommand != "rm":
            resolved_model = shortnames.resolve(args.MODEL)
            if resolved_model:
                args.UNRESOLVED_MODEL = args.MODEL
                args.MODEL = resolved_model

        # TODO: This is a hack. Once we have more typing in place these special cases
        # _should_ be removed.
        if not hasattr(args, "model"):
            args.model = args.MODEL

    # Validate that --add-to-unit is only used with --generate and its format is <section>:<key>:<value>
    if hasattr(args, "add_to_unit") and (add_to_units := args.add_to_unit):
        if getattr(args, "generate", None) is None:
            parser = get_parser()
            parser.error("--add-to-unit can only be used with --generate")
        if not (all(len([value for value in unit_to_add.split(":", 2) if value]) == 3 for unit_to_add in add_to_units)):
            parser = get_parser()
            parser.error("--add-to-unit parameters must be of the form <section>:<key>:<value>")

    if hasattr(args, "runtime_args"):
        args.runtime_args = shlex.split(args.runtime_args)

    # MLX runtime automatically requires --nocontainer
    if getattr(args, "runtime", None) == "mlx":
        if getattr(args, "container", None) is True:
            logger.info("MLX runtime automatically uses --nocontainer mode")
        args.container = False

    if hasattr(args, 'pull'):
        args.pull = normalize_pull_arg(args.pull, getattr(args, 'engine', None))

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
    registry = registry or CONFIG.transport

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
            perror(f"Broken symlink found in: {args.store}/models/{path} \nAttempting removal")
            New(str(path).replace("/", "://", 1), args).remove(args)

    return sorted(models, key=lambda p: os.path.getmtime(p), reverse=True)


def bench_cli(args):
    model = New(args.MODEL, args)
    model.ensure_model_exists(args)
    model.bench(args, assemble_command(args))


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
    parser = subparsers.add_parser(
        "list", aliases=["ls"], help="list all downloaded AI Models (excluding partially downloaded ones)"
    )
    parser.add_argument("--all", dest="all", action="store_true", help="include partially downloaded AI Models")
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


def _list_models_from_store(args):
    models = GlobalModelStore(args.store).list_models(engine=args.engine, show_container=args.container)

    ret = []
    local_timezone = datetime.now().astimezone().tzinfo

    for model, files in models.items():
        is_partially_downloaded = any(file.is_partial for file in files)
        if not args.all and is_partially_downloaded:
            continue

        model = trim_model_name(model)
        size_sum = 0
        last_modified = 0.0
        for file in files:
            size_sum += file.size
            last_modified = max(file.modified, last_modified)

        ret.append(
            {
                "name": f"{model} (partial)" if is_partially_downloaded else model,
                "modified": datetime.fromtimestamp(last_modified, tz=local_timezone).isoformat(),
                "size": size_sum,
            }
        )

    return ret


def _list_models(args):
    return _list_models_from_store(args)


def info_cli(args):
    info = {
        "Accelerator": get_accel(),
        "Config": load_file_config(),
        "Engine": {
            "Name": args.engine,
        },
        "Image": accel_image(CONFIG),
        "Inference": {
            "Default": args.runtime,
            "Engines": {spec: str(path) for spec, path in get_inference_spec_files().items()},
            "Schema": {schema: str(path) for schema, path in get_inference_schema_files().items()},
        },
        "RagImage": rag_image(CONFIG),
        "Selinux": CONFIG.selinux,
        "Shortnames": {
            "Files": shortnames.paths,
            "Names": shortnames.shortnames,
        },
        "Store": args.store,
        "UseContainer": args.container,
        "Version": version(),
    }
    if args.engine and len(args.engine) > 0:
        info["Engine"]["Info"] = engine.info(args)

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
    parser.add_argument(
        "--verify",
        default=CONFIG.verify,
        action=CoerceToBool,
        help="verify the model after pull, disable to allow pulling of models with different endianness",
    )
    parser.add_argument("MODEL", completer=suppressCompleter)  # positional argument
    parser.set_defaults(func=pull_cli)


def pull_cli(args):
    model = New(args.MODEL, args)
    model.pull(args)


def convert_parser(subparsers):
    parser = subparsers.add_parser(
        "convert",
        help="convert AI Model from local storage to OCI Image",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--carimage",
        default=CONFIG.carimage,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--gguf",
        choices=get_args(GGUF_QUANTIZATION_MODES),
        nargs="?",
        const=CONFIG.gguf_quantization_mode,  # Used if --gguf is provided without value
        default=None,  # Used if --gguf is not provided
        help=f"GGUF quantization format. If specified without value, {CONFIG.gguf_quantization_mode} is used.",
    )
    add_network_argument(parser)
    parser.add_argument(
        "--rag-image",
        default=rag_image(CONFIG),
        help="Image to use for conversion to GGUF",
        action=OverrideDefaultAction,
        completer=local_images,
    )
    parser.add_argument(
        "--image",
        default=accel_image(CONFIG),
        help="Image to use for quantization",
        action=OverrideDefaultAction,
        completer=local_images,
    )
    parser.add_argument(
        "--pull",
        dest="pull",
        type=str,
        default=CONFIG.pull,
        choices=["always", "missing", "never", "newer"],
        help="pull image policy",
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
    parser.add_argument("SOURCE")  # positional argument
    parser.add_argument("TARGET")  # positional argument
    parser.set_defaults(func=convert_cli)


def convert_cli(args):
    if not args.container:
        raise ValueError("convert command cannot be run with the --nocontainer option.")

    target = args.TARGET
    tgt = shortnames.resolve(target)
    if not tgt:
        tgt = target

    model = TransportFactory(tgt, args).create_oci()

    source_model = _get_source_model(args)
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
        default=CONFIG.carimage,
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
    if not smodel.exists() and not args.dryrun:
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
            m = TransportFactory(target, args).create_oci()
            m.push(source_model, args)
        except Exception as e1:
            logger.debug(e1)
            raise e


def runtime_options(parser, command):
    if command in ["run", "serve"]:
        parser.add_argument(
            "--api",
            default=CONFIG.api,
            choices=["llama-stack", "none"],
            help="unified API layer for for Inference, RAG, Agents, Tools, Safety, Evals, and Telemetry.",
        )
    parser.add_argument("--authfile", help="path of the authentication file")
    if command in ["run", "perplexity", "serve"]:
        parser.add_argument(
            "--cache-reuse",
            dest="cache_reuse",
            type=int,
            default=CONFIG.cache_reuse,
            help="min chunk size to attempt reusing from the cache via KV shifting",
            completer=suppressCompleter,
        )
        parser.add_argument(
            "-c",
            "--ctx-size",
            dest="context",
            type=int,
            default=CONFIG.ctx_size,
            help="size of the prompt context (0 = loaded from model)",
            completer=suppressCompleter,
        )
        parser.add_argument(
            "--max-model-len",
            dest="context",
            type=int,
            default=CONFIG.ctx_size,
            help=argparse.SUPPRESS,
            completer=suppressCompleter,
        )
    if command == "serve":
        parser.add_argument(
            "-d", "--detach", action="store_true", dest="detach", help="run the container in detached mode"
        )
    parser.add_argument(
        "--device",
        dest="device",
        action='append',
        type=str,
        help="device to leak in to the running container (or 'none' to pass no device)",
    )
    parser.add_argument(
        "--env",
        dest="env",
        action='append',
        type=str,
        default=CONFIG.env,
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
            "--add-to-unit",
            dest="add_to_unit",
            action='append',
            type=str,
            help="add KEY VALUE pair to generated unit file in the section SECTION (only valid with --generate)",
            metavar="SECTION:KEY:VALUE",
        )
        parser.add_argument(
            "--host",
            default=CONFIG.host,
            help="IP address to listen",
            completer=suppressCompleter,
        )
    parser.add_argument(
        "--image",
        default=accel_image(CONFIG),
        help="OCI container image to run with the specified AI model",
        action=OverrideDefaultAction,
        completer=local_images,
    )
    parser.add_argument(
        "--keep-groups",
        dest="podman_keep_groups",
        default=CONFIG.keep_groups,
        action="store_true",
        help="""pass `--group-add keep-groups` to podman.
If GPU device on host is accessible to via group access, this option leaks the user groups into the container.""",
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
    if command in ["run", "perplexity", "serve"]:
        parser.add_argument(
            "--max-tokens",
            dest="max_tokens",
            type=int,
            default=CONFIG.max_tokens,
            help="maximum number of tokens to generate (0 = unlimited)",
            completer=suppressCompleter,
        )
    add_network_argument(parser, dflt=None)
    parser.add_argument(
        "--ngl",
        dest="ngl",
        type=int,
        default=CONFIG.ngl,
        help="number of layers to offload to the gpu, if available",
        completer=suppressCompleter,
    )
    parser.add_argument(
        "--thinking",
        default=CONFIG.thinking,
        help="enable/disable thinking mode in reasoning models",
        action=CoerceToBool,
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
            default=CONFIG.port,
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
        default=CONFIG.pull,
        choices=["always", "missing", "never", "newer"],
        help='pull image policy',
    )
    if command in ["run", "serve"]:
        parser.add_argument(
            "--rag", help="RAG vector database or OCI Image to be served with the model", completer=local_models
        )
        parser.add_argument(
            "--rag-image",
            default=rag_image(CONFIG),
            help="OCI container image to run with the specified RAG data",
            action=OverrideDefaultAction,
            completer=local_images,
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
        "--selinux",
        default=CONFIG.selinux,
        action=CoerceToBool,
        help="Enable SELinux container separation",
    )
    parser.add_argument(
        "--temp",
        default=CONFIG.temp,
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
        parser.add_argument(
            "--dri",
            dest="dri",
            choices=["on", "off"],
            default="on",
            help="mount /dev/dri into the container when running llama-stack (default: on)",
        )


def default_threads():
    if CONFIG.threads < 0:
        nproc = os.cpu_count()
        if nproc and nproc > 4:
            return int(nproc / 2)

        return 4

    return CONFIG.threads


def chat_run_options(parser):
    parser.add_argument(
        '--color',
        '--colour',
        default="auto",
        choices=get_args(COLOR_OPTIONS),
        help='possible values are "never", "always" and "auto".',
    )
    parser.add_argument("--prefix", type=str, help="prefix for the user prompt", default=default_prefix())
    parser.add_argument("--mcp", nargs="*", help="MCP servers to use for the chat")


def chat_parser(subparsers):
    parser = subparsers.add_parser("chat", help="OpenAI chat with the specified RESTAPI URL")
    parser.add_argument(
        "--api-key",
        type=str,
        default=CONFIG.api_key,
        help="""OpenAI-compatible API key.
        Can also be set in ramalama.conf or via the RAMALAMA_API_KEY environment variable.""",
    )
    chat_run_options(parser)
    parser.add_argument(
        "--list",
        "--ls",
        action="store_true",
        help="list the available models at an endpoint",
    )
    parser.add_argument("--url", type=str, default="http://127.0.0.1:8080/v1", help="the url to send requests to")
    parser.add_argument("--model", "-m", type=str, completer=local_models, help="model for inferencing")
    parser.add_argument("--rag", type=str, help="a file or directory to use as context for the chat")
    parser.add_argument(
        "ARGS", nargs="*", help="overrides the default prompt, and the output is returned without entering the chatbot"
    )
    parser.set_defaults(func=chat.chat)


def _rag_args(args):
    args.noout = not args.debug
    rag_args = copy.copy(args)
    rag_args.subcommand = f"{args.subcommand} --rag"
    rag_args.MODEL = args.rag
    rag_args.image = args.rag_image
    if args.engine == "podman":
        rag_args.model_host = "host.containers.internal"
    else:
        rag_args.model_host = f"host.{args.engine}.internal"
    # If --name was specified, use it for the RAG proxy
    args.name = None
    # If --port was specified, use it for the RAG proxy, and
    # select a random port for the model
    args.port = None
    rag_args.model_port = args.port = compute_serving_port(args, exclude=[rag_args.port])
    rag_args.model_args = args
    rag_args.generate = ""
    return rag_args


def run_parser(subparsers):
    parser = subparsers.add_parser("run", help="run specified AI Model as a chatbot")
    runtime_options(parser, "run")
    chat_run_options(parser)
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
    try:
        # detect available port and update arguments
        args.port = compute_serving_port(args)

        model = New(args.MODEL, args)
        model.ensure_model_exists(args)
    except KeyError as e:
        logger.debug(e)
        try:
            args.quiet = True
            model = TransportFactory(args.MODEL, args, ignore_stderr=True).create_oci()
            model.ensure_model_exists(args)
        except Exception as exc:
            raise e from exc

    if args.rag:
        if not args.container:
            raise ValueError("ramalama run --rag cannot be run with the --nocontainer option.")
        args = _rag_args(args)
        model = RagTransport(model, assemble_command(args.model_args), args)
        model.ensure_model_exists(args)

    model.run(args, assemble_command(args))


def serve_parser(subparsers):
    parser = subparsers.add_parser("serve", help="serve REST API on specified AI Model")
    runtime_options(parser, "serve")
    parser.add_argument("MODEL", completer=local_models)  # positional argument
    parser.set_defaults(func=serve_cli)


def serve_cli(args):
    if not args.container:
        args.detach = False

    if args.api == "llama-stack":
        if not args.container:
            raise ValueError("ramalama serve --api llama-stack command cannot be run with the --nocontainer option.")

        stack = Stack(args)
        return stack.serve()

    try:
        # detect available port and update arguments
        args.port = compute_serving_port(args)

        model = New(args.MODEL, args)
        model.ensure_model_exists(args)
    except KeyError as e:
        try:
            args.quiet = True
            model = TransportFactory(args.MODEL, args, ignore_stderr=True).create_oci()
            model.ensure_model_exists(args)
        except Exception:
            raise e

    if args.rag:
        if not args.container:
            raise ValueError("ramalama serve --rag cannot be run with the --nocontainer option.")
        args = _rag_args(args)
        model = RagTransport(model, assemble_command(args.model_args), args)
        model.ensure_model_exists(args)

    model.serve(args, assemble_command(args))


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


def daemon_parser(subparsers):
    parser: ArgumentParserWithDefaults = subparsers.add_parser("daemon", help="daemon operations")
    parser.set_defaults(func=lambda _: parser.print_help())

    daemon_parsers = parser.add_subparsers(dest="daemon_command")

    start_parser = daemon_parsers.add_parser("start")
    start_parser.add_argument(
        "--image",
        default=accel_image(CONFIG),
        help="OCI container image to run with the specified AI model",
        action=OverrideDefaultAction,
        completer=local_images,
    )
    start_parser.add_argument(
        "--pull",
        dest="pull",
        type=str,
        default=CONFIG.pull,
        choices=["always", "missing", "never", "newer"],
        help='pull image policy',
    )
    start_parser.add_argument(
        "--host",
        default=CONFIG.host,
        help="IP address to listen",
        completer=suppressCompleter,
    )
    start_parser.add_argument(
        "-p",
        "--port",
        type=parse_port_option,
        default=CONFIG.port,
        help="port for AI Model server to listen on",
        completer=suppressCompleter,
    )
    start_parser.set_defaults(func=daemon_start_cli)

    run_parser = daemon_parsers.add_parser("run")
    run_parser.add_argument(
        "--host",
        default=CONFIG.host,
        help="IP address to listen",
        completer=suppressCompleter,
    )
    run_parser.add_argument(
        "-p",
        "--port",
        type=parse_port_option,
        default=CONFIG.port,
        help="port for AI Model server to listen on",
        completer=suppressCompleter,
    )
    run_parser.set_defaults(func=daemon_run_cli)


def daemon_start_cli(args):
    from ramalama.common import exec_cmd

    daemon_cmd = []
    daemon_model_store_dir = args.store
    is_daemon_in_container = args.container and args.engine in get_args(SUPPORTED_ENGINES)

    if is_daemon_in_container:
        # If run inside a container, map the model store to the container internal directory
        daemon_model_store_dir = "/ramalama/models"

        daemon_cmd += [
            args.engine,
            "run",
            "--pull",
            args.pull,
            "-d",
            "-p",
            f"{args.port}:8080",
            "-v",
            f"{args.store}:{daemon_model_store_dir}",
            args.image,
        ]

    daemon_cmd += [
        "ramalama",
        "--store",
        daemon_model_store_dir,
        "daemon",
        "run",
        "--port",
        "8080" if is_daemon_in_container else args.port,
        "--host",
        CONFIG.host if is_daemon_in_container else args.host,
    ]
    exec_cmd(daemon_cmd)


def daemon_run_cli(args):
    from ramalama.daemon.daemon import run

    run(host=args.host, port=int(args.port), model_store_path=args.store)


def version_parser(subparsers):
    parser = subparsers.add_parser("version", help="display version of RamaLama")
    parser.set_defaults(func=print_version)


class AddPathOrUrl(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, [])
        namespace.urls = []
        for value in values:
            parsed = urlparse(value)
            if parsed.scheme in ["file", ""] and parsed.netloc == "":
                getattr(namespace, self.dest).append(parsed.path.rstrip("/"))
            else:
                namespace.urls.append(value)


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
        default=CONFIG.env,
        help="environment variables to add to the running RAG container",
        completer=local_env,
    )
    parser.add_argument(
        "--format",
        default=CONFIG.rag_format,
        help="Output format for RAG Data",
        choices=["qdrant", "json", "markdown", "milvus"],
    )
    parser.add_argument(
        "--image",
        default=rag_image(CONFIG),
        help="Image to use for generating RAG data",
        action=OverrideDefaultAction,
        completer=local_images,
    )
    parser.add_argument(
        "--keep-groups",
        dest="podman_keep_groups",
        default=CONFIG.keep_groups,
        action="store_true",
        help="""pass `--group-add keep-groups` to podman.
If GPU device on host is accessible to via group access, this option leaks the user groups into the container.""",
    )
    add_network_argument(parser, dflt=None)
    parser.add_argument(
        "--pull",
        dest="pull",
        type=str,
        default=CONFIG.pull,
        choices=["always", "missing", "never", "newer"],
        help='pull image policy',
    )
    parser.add_argument(
        "--selinux",
        default=CONFIG.selinux,
        action=CoerceToBool,
        help="Enable SELinux container separation",
    )
    parser.add_argument(
        "PATHS",
        nargs="+",
        help=dedent(
            """
        Files/URLs/Directory containing PDF, DOCX, PPTX, XLSX, HTML, AsciiDoc & Markdown
        formatted files to be processed"""
        ),
        action=AddPathOrUrl,
    )
    parser.add_argument(
        "DESTINATION", help="Path or OCI Image name to contain processed rag data", completer=suppressCompleter
    )
    parser.add_argument(
        "--ocr",
        dest="ocr",
        default=CONFIG.ocr,
        action="store_true",
        help="Enable embedded image text extraction from PDF (Increases RAM Usage significantly)",
    )
    parser.set_defaults(func=rag_cli)


def rag_cli(args):
    rag = Rag(args.DESTINATION)
    args.inputdir = INPUT_DIR
    rag.generate(args, assemble_command(args))


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
                m = TransportFactory(model, args, ignore_stderr=True).create_oci()
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

    failed_models = []
    for model in models.keys():
        try:
            _rm_model([model], args)
        except Exception as e:
            failed_models.append((model, str(e)))
    if failed_models:
        for model, error in failed_models:
            perror(f"Failed to remove model '{model}': {error}")
        failed_names = ', '.join([model for model, _ in failed_models])
        raise Exception(f"Failed to remove the following models: {failed_names}")


def perplexity_parser(subparsers):
    parser = subparsers.add_parser("perplexity", help="calculate perplexity for specified AI Model")
    runtime_options(parser, "perplexity")
    parser.add_argument("MODEL", completer=local_models)  # positional argument
    parser.set_defaults(func=perplexity_cli)


def perplexity_cli(args):
    model = New(args.MODEL, args)
    model.ensure_model_exists(args)
    model.perplexity(args, assemble_command(args))


def inspect_parser(subparsers):
    parser = subparsers.add_parser("inspect", help="inspect an AI Model")
    parser.add_argument("--all", dest="all", action="store_true", help="display all available information of AI Model")
    parser.add_argument(
        "--get",
        dest="get",
        type=str,
        default="",
        completer=available_metadata,
        help="display specific metadata field of AI Model",
    )
    parser.add_argument("--json", dest="json", action="store_true", help="display AI Model information in JSON format")
    parser.add_argument("MODEL", completer=local_models)  # positional argument
    parser.set_defaults(func=inspect_cli)


def inspect_cli(args):
    args.pull = "never"
    model = New(args.MODEL, args)
    model.inspect(args.all, args.get == "all", args.get, args.json, args.dryrun)


def main():
    def eprint(e, exit_code):
        perror("Error: " + str(e).strip("'\""))
        sys.exit(exit_code)

    parser: ArgumentParserWithDefaults
    args: argparse.Namespace
    try:
        parser, args = init_cli()
        try:
            import argcomplete

            argcomplete.autocomplete(parser)
        except Exception:
            pass

        if not args.subcommand:
            parser.print_usage()
            perror("ramalama: requires a subcommand")
            return 0

        args.func(args)
    except urllib.error.HTTPError as e:
        eprint(f"pulling {e.geturl()} failed: {e}", errno.EINVAL)
    except HelpException:
        parser.print_help()
    except (ConnectionError, IndexError, KeyError, ValueError, NoRefFileFound) as e:
        eprint(e, errno.EINVAL)
    except NotImplementedError as e:
        eprint(e, errno.ENOSYS)
    except subprocess.CalledProcessError as e:
        eprint(e, e.returncode)
    except EndianMismatchError:
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)
    except IOError as e:
        eprint(e, errno.EIO)
    except ParseError as e:
        eprint(f"Failed to parse model: {e}", errno.EINVAL)
    except SafetensorModelNotSupported:
        eprint(
            f"""Safetensor models are not supported. Please convert it to GGUF via:
$ ramalama convert --gguf=<quantization> {args.model} <oci-name>
$ ramalama run <oci-name>
""",
            errno.ENOTSUP,
        )
    except NoGGUFModelFileFound:
        eprint(f"No GGUF model file found for downloaded model '{args.model}'", errno.ENOENT)
