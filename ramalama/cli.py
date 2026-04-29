from __future__ import annotations

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
from functools import lru_cache
from typing import Any, Optional, get_args
from urllib.parse import urlparse

# if autocomplete doesn't exist, just do nothing, don't break
try:
    import argcomplete

    suppressCompleter: Optional[type[argcomplete.completers.SuppressCompleter]] = (
        argcomplete.completers.SuppressCompleter
    )
except Exception:
    suppressCompleter = None

from ramalama import engine
from ramalama.arg_types import DefaultArgsType
from ramalama.cli_arg_normalization import normalize_pull_arg
from ramalama.common import accel_image, exec_cmd, get_accel, perror
from ramalama.config import (
    SUPPORTED_ENGINES,
    ActiveConfig,
    coerce_to_bool,
    load_file_config,
)
from ramalama.config_types import COLOR_OPTIONS
from ramalama.endian import EndianMismatchError
from ramalama.log_levels import LogLevel
from ramalama.logger import configure_logger, logger
from ramalama.model_inspect.error import ParseError
from ramalama.model_store.global_store import GlobalModelStore
from ramalama.plugins.loader import get_all_runtimes, get_runtime
from ramalama.prompt_utils import default_prefix
from ramalama.rag import rag_image
from ramalama.shortnames import Shortnames
from ramalama.stack import stack_image
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

GENERATE_OPTIONS = ["quadlet", "kube", "quadlet/kube", "compose"]
LIST_SORT_FIELD_OPTIONS = ["size", "modified", "name"]
LIST_SORT_ORDER_OPTIONS = ["desc", "asc"]


@lru_cache(maxsize=1)
def default_image() -> str:
    return accel_image(ActiveConfig())


@lru_cache(maxsize=1)
def default_rag_image() -> str:
    return rag_image(ActiveConfig())


@lru_cache(maxsize=1)
def default_stack_image() -> str:
    return stack_image(ActiveConfig())


@lru_cache(maxsize=1)
def default_tools_image() -> str:
    from ramalama.tools import tools_image

    return tools_image(ActiveConfig())


@lru_cache(maxsize=1)
def get_shortnames():
    return Shortnames()


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
    if generate.count(":") > 0:
        generate, output_dir = generate.split(":", 1)
    if output_dir == "":
        output_dir = "."

    return ParsedGenerateInput(generate, output_dir)


def parse_port_option(option: str) -> str:
    port = int(option)
    if port <= 0 or port >= 65535:
        raise ValueError(f"Invalid port '{port}'")
    return option


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
        resolved_model = get_shortnames().resolve(parsed_args.MODEL)

        model = New(resolved_model, parsed_args)
        metadata: dict = getattr(model, "inspect_metadata", lambda: {})()
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
            action.completer = completer  # type: ignore[attr-defined]
        return action


def get_initial_parser():
    description = get_description()
    parser = create_argument_parser(description, add_help=False)
    return parser


def get_parser():
    description = get_description()
    parser = create_argument_parser(description, add_help=True)
    configure_subcommands(parser)
    return parser


def init_cli():
    """Initialize the RamaLama CLI and parse command line arguments."""
    return parse_args_from_cmd(sys.argv[1:])


def parse_args_from_cmd(cmd: list[str]) -> tuple[argparse.ArgumentParser, argparse.Namespace]:
    """Parse arguments based on a command string"""
    config = ActiveConfig()
    if any(arg in ("--dryrun", "--dry-run", "--generate") or arg.startswith("--generate=") for arg in sys.argv[1:]):
        config.dryrun = True
    # Phase 1: Parse the initial arguments to set CONFIG.runtime etc... as this can affect the subcommands
    initial_parser = get_initial_parser()
    initial_args, _ = initial_parser.parse_known_args(cmd)
    for arg in initial_args.__dict__.keys() & config._fields:
        if getattr(initial_args, arg) != getattr(config, arg):
            setattr(config, arg, getattr(initial_args, arg))

    # Phase 2: Re-parse the arguments with the subcommands enabled
    parser = get_parser()
    args = parser.parse_args(cmd)
    post_parse_setup(args)

    # Update config field that store runtime specific config which can be overridden via the cli
    # e.g Config.image and Config.rag_image etc...
    # TODO(owalsh): refactor this to remove runtime specific config from the global config object
    for arg in args.__dict__.keys() & config._fields:
        if getattr(args, arg) != getattr(config, arg):
            setattr(config, arg, getattr(args, arg))
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


def abspath(astring) -> str:
    return os.path.abspath(astring)


def create_argument_parser(description: str, add_help: bool = True):
    """Create and configure the argument parser for the CLI."""
    parser = ArgumentParserWithDefaults(
        prog="ramalama",
        description=description,
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=add_help,
    )
    parser.add_argument("-v", "--version", action="version", version="%(prog)s version " + version())
    configure_arguments(parser)
    return parser


def configure_arguments(parser):
    """Configure the command-line arguments for the parser."""
    config = ActiveConfig()
    verbosity_group = parser.add_mutually_exclusive_group()
    parser.add_argument(
        "--container",
        dest="container",
        default=config.container,
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
        default=config.engine,
        choices=get_args(SUPPORTED_ENGINES),
        help="""run RamaLama using the specified container engine.
The RAMALAMA_CONTAINER_ENGINE environment variable modifies default behaviour.""",
    )
    parser.add_argument(
        "--nocontainer",
        dest="container",
        default=not config.container,
        action="store_false",
        help="""do not run RamaLama in the default container.
The RAMALAMA_IN_CONTAINER environment variable modifies default behaviour.""",
    )
    verbosity_group.add_argument(
        "--quiet",
        "-q",
        dest="quiet",
        action="store_true",
        help="Reduce output verbosity (silences warnings, simplifies list output)",
    )
    parser.add_argument(
        "--runtime",
        default=config.runtime,
        choices=list(get_all_runtimes().keys()),
        help="specify the inference engine runtime to use",
    )
    parser.add_argument(
        "--store",
        default=config.store,
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
    # Register subcommands only for the selected runtime plugin so that help
    # output only shows subcommands the active runtime actually supports.
    # get_config().runtime is already set by Phase 1 of parse_args_from_cmd
    # before configure_subcommands() is called in Phase 2.
    # These include the subcommands serve and run, which are handled
    # in BaseInferenceRuntime and its subclasses
    runtime = ActiveConfig().runtime
    get_runtime(runtime).register_subcommands(subparsers)
    chat_parser(subparsers)
    containers_parser(subparsers)
    help_parser(subparsers)
    info_parser(subparsers)
    inspect_parser(subparsers)
    list_parser(subparsers)
    login_parser(subparsers)
    logout_parser(subparsers)
    pull_parser(subparsers)
    push_parser(subparsers)
    rm_parser(subparsers)
    sandbox_parser(subparsers)
    stop_parser(subparsers)
    version_parser(subparsers)
    daemon_parser(subparsers)


def post_parse_setup(args):
    """Perform additional setup after parsing arguments."""
    if getattr(args, "subcommand", None) == "benchmark":
        args.subcommand = "bench"

    def map_https_to_transport(input: str) -> str:
        if input.startswith("https://") or input.startswith("http://"):
            url = urlparse(input)
            # detect if the whole repo is defined or a specific file
            if url.path.count("/") != 2:
                return input
            if url.hostname in ["hf.co", "huggingface.co"]:
                return f"hf:/{url.path}"
            if url.hostname in ["ollama.com"]:
                return f"ollama:/{url.path}"
        return input

    # Resolve the model input
    # First, map https:// inputs to ollama or huggingface based on url domain
    # Then resolve the input based on the available shortname list
    if getattr(args, "MODEL", None):
        shortnames = get_shortnames()
        if isinstance(args.MODEL, str):
            args.INITIAL_MODEL = args.MODEL
            args.MODEL = map_https_to_transport(args.MODEL)

            args.UNRESOLVED_MODEL = args.MODEL
            args.MODEL = shortnames.resolve(args.MODEL)

        if isinstance(args.MODEL, list):
            args.INITIAL_MODEL = [m for m in args.MODEL]
            for i in range(len(args.MODEL)):
                args.MODEL[i] = map_https_to_transport(args.MODEL[i])

            args.UNRESOLVED_MODEL = [m for m in args.MODEL]
            for i in range(len(args.MODEL)):
                args.MODEL[i] = shortnames.resolve(args.MODEL[i])

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

    if hasattr(args, 'pull'):
        args.pull = normalize_pull_arg(args.pull, getattr(args, 'engine', None))

    # Determine log level: debug > quiet > config > default
    if args.debug:
        log_level = LogLevel.DEBUG
    elif getattr(args, 'quiet', False):
        log_level = LogLevel.ERROR
    else:
        log_level = ActiveConfig().log_level or LogLevel.WARNING
    configure_logger(log_level)

    # Allow the runtime plugin to mutate and validate args after logger is configured
    # (e.g. MlxPlugin enforces Apple Silicon and sets args.container = False)
    runtime = getattr(args, "runtime", None)
    if runtime is not None:
        get_runtime(runtime).post_process_args(args)


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
    registry = registry or ActiveConfig().transport

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


def add_network_argument(parser, dflt: Optional[str] = "none"):
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
    parser.add_argument(
        "--shortnames",
        dest="shortnames",
        action="store_true",
        help="display available shortnames",
    )
    parser.set_defaults(func=info_cli)


def list_parser(subparsers):
    parser = subparsers.add_parser(
        "list", aliases=["ls"], help="list all downloaded AI Models (excluding partially downloaded ones)"
    )
    parser.add_argument("--all", dest="all", action="store_true", help="include partially downloaded AI Models")
    parser.add_argument("--json", dest="json", action="store_true", help="print using json")
    parser.add_argument("-n", "--noheading", dest="noheading", action="store_true", help="do not display heading")
    parser.add_argument(
        "--sort",
        dest="sort",
        choices=LIST_SORT_FIELD_OPTIONS,
        default="name",
        help="field used to sort the AI Models",
    )
    parser.add_argument(
        "--order",
        dest="order",
        choices=LIST_SORT_ORDER_OPTIONS,
        default="desc",
        help="order used to sort the AI Models",
    )
    parser.set_defaults(func=list_cli)


def human_readable_size(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            size = round(size, 2)
            return f"{size} {unit}"

        size /= 1024

    return f"{size} PB"


def _list_models_from_store(args):

    models = GlobalModelStore(args.store).list_models(engine=args.engine, show_container=args.container)

    ret = []
    local_timezone = datetime.now().astimezone().tzinfo

    # map the listed models to the proper output structure for display
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

    # sort the listed models according to the desired order
    ret.sort(key=lambda entry: entry[args.sort], reverse=args.order == "desc")

    return ret


def _list_models(args):
    return _list_models_from_store(args)


def info_cli(args: DefaultArgsType) -> None:
    shortnames = get_shortnames()
    if getattr(args, 'shortnames', None):
        for name in sorted(shortnames.shortnames):
            config_source = shortnames.config_sources.get(name)
            source = shortnames.shortnames[name]

            message = f"{name}={source} ({config_source})"
            print(message)
        return
    info: dict[str, Any] = {
        "Accelerator": get_accel(),
        "Config": load_file_config(),
        "Engine": {
            "Name": args.engine,
        },
        "Image": default_image(),
        "Runtimes": {
            "Default": args.runtime,
            "Available": list(get_all_runtimes().keys()),
        },
        "RagImage": default_rag_image(),
        "Selinux": ActiveConfig().selinux,
        "Shortnames": {
            "Files": shortnames.paths,
            "Names": shortnames.shortnames,
            "Sources": list(set(shortnames.config_sources.values())),
        },
        "Store": args.store,
        "ToolsImage": default_tools_image(),
        "UseContainer": args.container,
        "Version": version(),
    }
    if args.engine and len(args.engine) > 0:
        from ramalama import engine

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
    config = ActiveConfig()
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
        default=config.verify,
        action=CoerceToBool,
        help="verify the model after pull, disable to allow pulling of models with different endianness",
    )
    parser.add_argument("MODEL", completer=suppressCompleter)  # positional argument
    parser.set_defaults(func=pull_cli)


def pull_cli(args):

    model = New(args.MODEL, args)
    model.pull(args)


def push_parser(subparsers):
    config = ActiveConfig()
    parser = subparsers.add_parser(
        "push",
        help="push AI Model from local storage to remote registry",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--authfile", help="path of the authentication file")
    parser.add_argument(
        "--carimage",
        default=config.carimage,
        help=argparse.SUPPRESS,
    )
    add_network_argument(parser)
    parser.add_argument(
        "--type",
        default=config.convert_type,
        choices=["artifact", "car", "raw"],
        help="""\
type of OCI Model Image to push.

Model "artifact" stores the AI Model as an OCI Artifact.
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


def _get_source_model(args, transport=None):
    shortnames = get_shortnames()
    src = shortnames.resolve(args.SOURCE)

    smodel = New(src, args, transport=transport)
    if smodel.type == "OCI":
        if not args.TARGET:
            return smodel
        raise ValueError(f"converting from an OCI based image {src} is not supported")
    if not smodel.exists() and not args.dryrun:
        smodel.pull(args)
    return smodel


def push_cli(args):

    target = args.SOURCE
    transport = None
    if not args.TARGET:
        transport = "oci"
    source_model = _get_source_model(args, transport=transport)

    if args.TARGET:
        shortnames = get_shortnames()
        if source_model.type == "OCI":
            raise ValueError(f"converting from an OCI based image {args.SOURCE} is not supported")
        target = shortnames.resolve(args.TARGET)

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
    config = ActiveConfig()
    parser.add_argument("--authfile", help="path of the authentication file")
    if command == "serve":
        parser.add_argument(
            "-d", "--detach", action="store_true", dest="detach", help="run the container in detached mode"
        )
        parser.add_argument(
            "--stack-image",
            default=default_stack_image(),
            help="OCI container image to run llama-stack server",
            action=OverrideDefaultAction,
            completer=local_images,
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
        default=config.env,
        help="environment variables to add to the running container",
        completer=local_env,
    )
    parser.add_argument(
        "--image",
        default=default_image(),
        help="OCI container image to run with the specified AI model",
        action=OverrideDefaultAction,
        completer=local_images,
    )
    parser.add_argument(
        "--keep-groups",
        dest="podman_keep_groups",
        default=config.keep_groups,
        action="store_true",
        help="""pass `--group-add keep-groups` to podman.
If GPU device on host is accessible to via group access, this option leaks the user groups into the container.""",
    )
    parser.add_argument(
        "-n",
        "--name",
        dest="name",
        help="name of container in which the Model will be run",
        completer=suppressCompleter,
    )
    add_network_argument(parser, dflt=None)
    parser.add_argument(
        "--oci-runtime",
        help="override the default OCI runtime used to launch the container",
        completer=suppressCompleter,
    )
    parser.add_argument(
        "--privileged", dest="privileged", action="store_true", help="give extended privileges to container"
    )
    parser.add_argument(
        "--pull",
        dest="pull",
        type=str,
        default=config.pull,
        choices=["always", "missing", "never", "newer"],
        help='pull image policy',
    )
    parser.add_argument("--seed", help="override random seed", completer=suppressCompleter)
    parser.add_argument(
        "--selinux",
        default=config.selinux,
        action=CoerceToBool,
        help="Enable SELinux container separation",
    )
    parser.add_argument(
        "--tls-verify",
        dest="tlsverify",
        default=True,
        help="require HTTPS and verify certificates when contacting registries",
    )


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
    parser.add_argument(
        "--summarize-after",
        type=int,
        default=ActiveConfig().summarize_after,
        metavar="N",
        help="automatically summarize conversation history after N messages to prevent context growth (0=disabled)",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="continue to interactive chat mode after processing stdin or prompt arguments",
    )


def _chat_cli(args):
    from ramalama import chat as chat_module

    return chat_module.chat(args)


def chat_parser(subparsers):
    parser = subparsers.add_parser("chat", help="OpenAI chat with the specified RESTAPI URL")
    parser.add_argument(
        "--api-key",
        type=str,
        default=ActiveConfig().api_key,
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
        "--max-tokens",
        dest="max_tokens",
        type=int,
        default=ActiveConfig().max_tokens,
        help="maximum number of tokens to generate (0 = unlimited)",
    )
    parser.add_argument(
        "--temp",
        type=float,
        default=float(ActiveConfig().temp),
        help="temperature of the response from the AI model",
    )
    parser.add_argument(
        "ARGS", nargs="*", help="overrides the default prompt, and the output is returned without entering the chatbot"
    )
    parser.set_defaults(func=_chat_cli)


def _rag_args(args):
    args.noout = not args.debug
    rag_args = copy.copy(args)
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
    # Remove port_override so compute_serving_port picks a random port
    # for the model container instead of returning the now-None args.port
    if hasattr(args, 'port_override'):
        delattr(args, 'port_override')
    rag_args.model_port = args.port = compute_serving_port(args, exclude=[rag_args.port])
    args.rag = None
    rag_args.model_args = args
    rag_args.generate = ""
    return rag_args


def sandbox_parser(subparsers):
    parser = subparsers.add_parser("sandbox", help="run an AI agent in a sandbox, backed by a local AI Model")
    parser.set_defaults(func=lambda _: parser.print_help())
    sandbox_subparsers = parser.add_subparsers(dest="sandbox_agent")

    from ramalama.sandbox import add_sandbox_subparsers

    for sub_parser in add_sandbox_subparsers(sandbox_subparsers, local_images, local_models):
        runtime_options(sub_parser, "sandbox")


def stop_parser(subparsers):
    parser = subparsers.add_parser("stop", help="stop named container that is running AI Model")
    parser.add_argument("-a", "--all", action="store_true", help="stop all RamaLama containers")
    parser.add_argument(
        "--ignore", action="store_true", help="ignore errors when specified RamaLama container is missing"
    )
    parser.add_argument("NAME", nargs="?", completer=local_containers)
    parser.set_defaults(func=stop_container)


def stop_container(args):
    from ramalama import engine

    if not args.all:
        engine.stop_container(args, args.NAME)
        return

    if args.NAME:
        raise ValueError(f"specifying --all and container name, {args.NAME}, not allowed")
    args.ignore = True
    args.format = "{{ .Names }}"
    for i in engine.containers(args):
        engine.stop_container(args, i)


def daemon_parser(subparsers) -> None:
    config = ActiveConfig()
    parser: ArgumentParserWithDefaults = subparsers.add_parser("daemon", help="daemon operations")
    parser.set_defaults(func=lambda _: parser.print_help())

    daemon_parsers = parser.add_subparsers(dest="daemon_command")

    start_parser = daemon_parsers.add_parser("start")
    start_parser.add_argument(
        "--image",
        default=default_image(),
        help="OCI container image to run with the specified AI model",
        action=OverrideDefaultAction,
        completer=local_images,
    )
    start_parser.add_argument(
        "--pull",
        dest="pull",
        type=str,
        default=config.pull,
        choices=["always", "missing", "never", "newer"],
        help='pull image policy',
    )
    start_parser.add_argument(
        "--host",
        default=config.host,
        help="IP address to listen",
        completer=suppressCompleter,
    )
    start_parser.add_argument(
        "-p",
        "--port",
        type=parse_port_option,
        default=config.port,
        help="port for AI Model server to listen on",
        completer=suppressCompleter,
    )
    start_parser.set_defaults(func=daemon_start_cli)

    run_parser = daemon_parsers.add_parser("run")
    run_parser.add_argument(
        "--host",
        default=config.host,
        help="IP address to listen",
        completer=suppressCompleter,
    )
    run_parser.add_argument(
        "-p",
        "--port",
        type=parse_port_option,
        default=config.port,
        help="port for AI Model server to listen on",
        completer=suppressCompleter,
    )
    run_parser.set_defaults(func=daemon_run_cli)


def daemon_start_cli(args):
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
        ActiveConfig().host if is_daemon_in_container else args.host,
    ]
    exec_cmd(daemon_cmd)


def daemon_run_cli(args):
    from ramalama.daemon.daemon import run

    run(host=args.host, port=int(args.port), model_store_path=args.store)


def version_parser(subparsers):
    parser = subparsers.add_parser("version", help="display version of RamaLama")
    parser.set_defaults(func=print_version)


def rm_parser(subparsers):
    parser = subparsers.add_parser("rm", help="remove AI Model from local storage")
    parser.add_argument("-a", "--all", action="store_true", help="remove all local Models")
    parser.add_argument("--ignore", action="store_true", help="ignore errors when specified Model does not exist")
    parser.add_argument("MODEL", nargs="*", completer=local_models)  # positional argument
    parser.set_defaults(func=rm_cli)


def _rm_oci_model(model, args) -> bool:
    # attempt to remove as a container image
    try:
        m = TransportFactory(model, args, ignore_stderr=True).create_oci()
        return m.remove(args)
    except Exception:
        return False


def _rm_model(models, args):
    exceptions = []
    shortnames = get_shortnames()

    for model in models:
        model = shortnames.resolve(model)

        try:
            m = New(model, args)
            m.remove(args)
        except (KeyError, subprocess.CalledProcessError) as e:
            for prefix in MODEL_TYPES:
                if model.startswith(prefix + "://"):
                    if not args.ignore:
                        raise e
            # attempt to remove as a container image
            if _rm_oci_model(model, args) or args.ignore:
                continue
            exceptions.append(e)

    if len(exceptions) > 0:
        for exception in exceptions[1:]:
            perror("Error: " + str(exception).strip("'\""))
        raise exceptions[0]


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
    parser.add_argument("MODEL", nargs="?", completer=local_models)  # positional argument
    parser.set_defaults(func=inspect_cli)


def inspect_cli(args):
    if not args.MODEL:
        parser = get_parser()
        parser.error("inspect requires MODEL")
    args.pull = "never"

    model = New(args.MODEL, args)
    inspect = model.inspect(args.all, args.get == "all", args.get, args.json, args.dryrun)  # type: ignore[call-arg]

    print(inspect)


def main() -> None:
    def eprint(e: Exception | str, exit_code: int):
        try:
            if args.debug:
                logger.exception(e)
        except Exception:
            pass
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
            return

        args.func(args)
    except urllib.error.HTTPError as e:
        eprint(f"pulling {e.geturl()} failed: {e}", errno.EINVAL)
    except FileNotFoundError as e:
        eprint(e, errno.ENOENT)
    except HelpException:
        parser.print_help()  # type: ignore[possibly-unbound]
    except (ConnectionError, IndexError, KeyError, ValueError, NoRefFileFound) as e:
        eprint(e, errno.EINVAL)
    except NotImplementedError as e:
        eprint(e, errno.ENOSYS)
    except subprocess.TimeoutExpired as e:
        eprint(e, errno.ETIMEDOUT)
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
        message = (
            "Safetensor models are not supported. Please convert it to GGUF via:\n"
            f"$ ramalama convert --gguf=<quantization> {args.model} <oci-name>\n"  # type: ignore[possibly-unbound]
            "$ ramalama run <oci-name>\n"
        )
        eprint(message, errno.ENOTSUP)
    except NoGGUFModelFileFound:
        eprint(f"No GGUF model file found for downloaded model '{args.model}'", errno.ENOENT)  # type: ignore
    except Exception as e:
        if isinstance(e, OSError) and hasattr(e, "winerror") and e.winerror == 206:
            eprint("Path too long, please enable long path support in the Windows registry", errno.ENAMETOOLONG)
        else:
            raise
