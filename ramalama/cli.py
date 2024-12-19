from pathlib import Path
import argparse
import glob
import json
import os
import subprocess
import time
import ramalama.oci

from ramalama.huggingface import Huggingface
from ramalama.common import (
    container_manager,
    default_image,
    perror,
    run_cmd,
)
from ramalama.model import model_types
from ramalama.oci import OCI
from ramalama.ollama import Ollama
from ramalama.url import URL
from ramalama.shortnames import Shortnames
from ramalama.toml_parser import TOMLParser
from ramalama.version import version, print_version

shortnames = Shortnames()


class HelpException(Exception):
    pass


def use_container():
    use_container = os.getenv("RAMALAMA_IN_CONTAINER")
    if use_container:
        return use_container.lower() == "true"

    conman = container_manager()
    return conman is not None


class ArgumentParserWithDefaults(argparse.ArgumentParser):
    def add_argument(self, *args, help=None, default=None, **kwargs):
        if help is not None:
            kwargs['help'] = help
        if default is not None and args[0] != '-h':
            kwargs['default'] = default
            if help is not None and help != "==SUPPRESS==":
                kwargs['help'] += ' (default: {})'.format(default)
        super().add_argument(*args, **kwargs)


def load_config():
    """Load configuration from a list of paths, in priority order."""
    parser = TOMLParser()
    config_path = os.getenv("RAMALAMA_CONFIG")
    if config_path:
        return parser.parse_file(config_path)

    config = {}
    config_paths = [
        "/usr/share/ramalama/ramalama.conf",
        "/etc/ramalama/ramalama.conf",
    ]
    config_home = os.getenv("XDG_CONFIG_HOME", os.path.join("~", ".config"))
    config_paths.extend([os.path.expanduser(os.path.join(config_home, "ramalama", "ramalama.conf"))])

    # Load configuration from each path
    for path in config_paths:
        if os.path.exists(path):
            # Load the main config file
            config = parser.parse_file(path)
        if os.path.isdir(path + ".d"):
            # Load all .conf files in ramalama.conf.d directory
            for conf_file in sorted(Path(path + ".d").glob("*.conf")):
                config = parser.parse_file(conf_file)

    return config


def get_store():
    if os.geteuid() == 0:
        return "/var/lib/ramalama"

    return os.path.expanduser("~/.local/share/ramalama")


def load_and_merge_config():
    """Load configuration from files and merge with environment variables."""
    config = load_config()
    ramalama_config = config.setdefault('ramalama', {})

    ramalama_config['container'] = os.getenv('RAMALAMA_IN_CONTAINER', ramalama_config.get('container', use_container()))
    ramalama_config['engine'] = os.getenv(
        'RAMALAMA_CONTAINER_ENGINE', ramalama_config.get('engine', container_manager())
    )
    ramalama_config['image'] = os.getenv('RAMALAMA_IMAGE', ramalama_config.get('image', default_image()))
    ramalama_config['nocontainer'] = ramalama_config.get('nocontainer', False)
    if ramalama_config['nocontainer']:
        ramalama_config['container'] = False
    else:
        ramalama_config['container'] = os.getenv(
            'RAMALAMA_IN_CONTAINER', ramalama_config.get('container', use_container())
        )

    ramalama_config['carimage'] = ramalama_config.get('carimage', "registry.access.redhat.com/ubi9-micro:latest")
    ramalama_config['runtime'] = ramalama_config.get('runtime', 'llama.cpp')
    ramalama_config['store'] = os.getenv('RAMALAMA_STORE', ramalama_config.get('store', get_store()))
    ramalama_config['transport'] = os.getenv('RAMALAMA_TRANSPORT', ramalama_config.get('transport', "ollama"))

    return ramalama_config


config = load_and_merge_config()


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
        default=config.get("container"),
        action="store_true",
        help="""run RamaLama in the default container.
The RAMALAMA_IN_CONTAINER environment variable modifies default behaviour.""",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="display debug messages",
    )
    parser.add_argument(
        "--dryrun", dest="dryrun", action="store_true", help="show container runtime command without executing it"
    )
    parser.add_argument("--dry-run", dest="dryrun", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--engine",
        dest="engine",
        default=config.get("engine"),
        help="""run RamaLama using the specified container engine.
The RAMALAMA_CONTAINER_ENGINE environment variable modifies default behaviour.""",
    )
    parser.add_argument(
        "--gpu",
        dest="gpu",
        default=False,
        action="store_true",
        help="offload the workload to the GPU",
    )
    parser.add_argument(
        "--image",
        default=config.get("image"),
        help="OCI container image to run with the specified AI model",
    )
    parser.add_argument(
        "--nocontainer",
        dest="container",
        default=config.get("nocontainer"),
        action="store_false",
        help="""do not run RamaLama in the default container.
The RAMALAMA_IN_CONTAINER environment variable modifies default behaviour.""",
    )
    parser.add_argument(
        "--runtime",
        default=config.get("runtime"),
        choices=["llama.cpp", "vllm"],
        help="specify the runtime to use; valid options are 'llama.cpp' and 'vllm'",
    )
    parser.add_argument(
        "--store",
        default=config.get("store"),
        help="store AI Models in the specified directory",
    )
    parser.add_argument("-v", "--version", dest="version", action="store_true", help="show RamaLama version")


def configure_subcommands(parser):
    """Add subcommand parsers to the main argument parser."""
    subparsers = parser.add_subparsers(dest="subcommand")
    subparsers.required = False
    help_parser(subparsers)
    containers_parser(subparsers)
    convert_parser(subparsers)
    info_parser(subparsers)
    list_parser(subparsers)
    login_parser(subparsers)
    logout_parser(subparsers)
    pull_parser(subparsers)
    push_parser(subparsers)
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


def login_parser(subparsers):
    parser = subparsers.add_parser("login", help="login to remote registry")
    # Do not run in a container
    parser.add_argument("--authfile", help="path of the authentication file")
    parser.add_argument("--container", default=False, action="store_false", help=argparse.SUPPRESS)
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
    parser.add_argument("--container", default=False, action="store_false", help=argparse.SUPPRESS)
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


def list_files_by_modification():
    paths = Path().rglob("*")
    models = []
    for path in paths:
        if str(path).startswith("file/"):
            if not os.path.exists(str(path)):
                path = str(path).replace("file/", "file:///")
                perror(f"{path} does not exist")
                continue
        models.append(path)

    return sorted(models, key=lambda p: os.path.getmtime(p), reverse=True)


def containers_parser(subparsers):
    parser = subparsers.add_parser("containers", aliases=["ps"], help="list all RamaLama containers")
    parser.add_argument("--container", default=False, action="store_false", help=argparse.SUPPRESS)
    parser.add_argument("--format", help="pretty-print containers to JSON or using a Go template")
    parser.add_argument("-n", "--noheading", dest="noheading", action="store_true", help="do not display heading")
    parser.add_argument("--no-trunc", dest="notrunc", action="store_true", help="display the extended information")
    parser.set_defaults(func=list_containers)


def _list_containers(args):
    conman = args.engine
    if conman == "":
        raise IndexError("no container manager (Podman, Docker) found")

    conman_args = [conman, "ps", "-a", "--filter", "label=RAMALAMA"]
    if args.noheading:
        conman_args += ["--noheading"]
    if hasattr(args, "notrunc") and args.notrunc:
        conman_args += ["--no-trunc"]

    if args.format:
        conman_args += [f"--format={args.format}"]

    try:
        output = run_cmd(conman_args).stdout.decode("utf-8").strip()
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
    parser = subparsers.add_parser("info", help="Display information pertaining to setup of RamaLama.")
    parser.add_argument("--container", default=False, action="store_false", help=argparse.SUPPRESS)
    parser.set_defaults(func=info_cli)


def list_parser(subparsers):
    parser = subparsers.add_parser("list", aliases=["ls"], help="list all downloaded AI Models")
    parser.add_argument("--container", default=False, action="store_false", help=argparse.SUPPRESS)
    parser.add_argument("--json", dest="json", action="store_true", help="print using json")
    parser.add_argument("-n", "--noheading", dest="noheading", action="store_true", help="do not display heading")
    parser.add_argument("-q", "--quiet", dest="quiet", action="store_true", help="print only Model names")
    parser.set_defaults(func=list_cli)


def human_readable_size(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            size = round(size, 2)
            return f"{size} {unit}"

        size /= 1024

    return f"{size} PB"


def get_size(file):
    return human_readable_size(os.path.getsize(file))


def _list_models(args):
    mycwd = os.getcwd()
    os.chdir(f"{args.store}/models/")
    models = []

    # Collect model data
    for path in list_files_by_modification():
        if path.is_symlink():
            if str(path).startswith("file/"):
                name = str(path).replace("/", ":///", 1)
            else:
                name = str(path).replace("/", "://", 1)
            file_epoch = path.lstat().st_mtime
            modified = int(time.time() - file_epoch)
            size = get_size(path)

            # Store data for later use
            models.append({"name": name, "modified": modified, "size": size})

    models.extend(ramalama.oci.list_models(args))

    os.chdir(mycwd)
    return models


def info_cli(args):
    info = {
        "Engine": args.engine,
        "Image": args.image,
        "Runtime": args.runtime,
        "Store": args.store,
        "Version": version(),
    }
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
            modified = human_duration(model["modified"]) + " ago"
        except TypeError:
            modified = model["modified"]
        name_width = max(name_width, len(model["name"]))
        modified_width = max(modified_width, len(modified))
        size_width = max(size_width, len(model["size"]))

    if not args.quiet and not args.noheading and not args.json:
        print(f"{'NAME':<{name_width}} {'MODIFIED':<{modified_width}} {'SIZE':<{size_width}}")

    for model in models:
        try:
            modified = human_duration(model["modified"]) + " ago"
        except TypeError:
            modified = model["modified"]
        if args.quiet:
            print(model["name"])
        else:
            print(f"{model['name']:<{name_width}} {modified:<{modified_width}} {model['size'].upper():<{size_width}}")


def help_parser(subparsers):
    parser = subparsers.add_parser("help", help="help about any command")
    # Do not run in a container
    parser.add_argument("--container", default=False, action="store_false", help=argparse.SUPPRESS)
    parser.set_defaults(func=help_cli)


def help_cli(args):
    raise HelpException()


def pull_parser(subparsers):
    parser = subparsers.add_parser("pull", help="pull AI Model from Model registry to local storage")
    parser.add_argument("--authfile", help="path of the authentication file")
    parser.add_argument("--container", default=False, action="store_false", help=argparse.SUPPRESS)
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
        default=config['carimage'],
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
    parser.add_argument("SOURCE")  # positional argument
    parser.add_argument("TARGET")  # positional argument
    parser.set_defaults(func=convert_cli)


def convert_cli(args):
    target = args.TARGET
    source = _get_source(args)

    tgt = shortnames.resolve(target)
    if not tgt:
        tgt = target

    model = OCI(tgt, args.engine)
    model.convert(source, args)


def push_parser(subparsers):
    parser = subparsers.add_parser(
        "push",
        help="push AI Model from local storage to remote registry",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--authfile", help="path of the authentication file")
    parser.add_argument("--container", default=False, action="store_false", help=argparse.SUPPRESS)
    parser.add_argument(
        "--carimage",
        default=config['carimage'],
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
        return src
    else:
        return smodel.path(args)


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
        for mtype in model_types:
            if tgt.startswith(mtype + "://"):
                raise e
        try:
            # attempt to push as a container image
            m = OCI(tgt, config.get('engine', container_manager()))
            m.push(source, args)
        except Exception:
            raise e


def _run(parser):
    parser.add_argument("--authfile", help="path of the authentication file")
    parser.add_argument(
        "-c",
        "--ctx-size",
        dest="context",
        default=config.get('ctx_size', 2048),
        help="size of the prompt context (0 = loaded from model)",
    )
    parser.add_argument("-n", "--name", dest="name", help="name of container in which the Model will be run")
    parser.add_argument("--seed", help="override random seed")
    parser.add_argument(
        "--temp", default=config.get('temp', "0.8"), help="temperature of the response from the AI model"
    )
    parser.add_argument(
        "--tls-verify",
        dest="tlsverify",
        default=True,
        help="require HTTPS and verify certificates when contacting registries",
    )


def run_parser(subparsers):
    parser = subparsers.add_parser("run", help="run specified AI Model as a chatbot")
    _run(parser)
    parser.add_argument("MODEL")  # positional argument
    parser.add_argument(
        "ARGS", nargs="*", help="Overrides the default prompt, and the output is returned without entering the chatbot"
    )
    parser.set_defaults(func=run_cli)


def run_cli(args):
    model = New(args.MODEL, args)
    model.run(args)


def serve_parser(subparsers):
    parser = subparsers.add_parser("serve", help="serve REST API on specified AI Model")
    _run(parser)
    parser.add_argument("-d", "--detach", action="store_true", dest="detach", help="run the container in detached mode")
    parser.add_argument("--host", default=config.get('host', "0.0.0.0"), help="IP address to listen")
    parser.add_argument(
        "--generate",
        choices=["quadlet", "kube", "quadlet/kube"],
        help="generate specified configuration format for running the AI Model as a service",
    )
    parser.add_argument(
        "-p", "--port", default=config.get('port', "8080"), help="port for AI Model server to listen on"
    )
    parser.add_argument("MODEL")  # positional argument
    parser.set_defaults(func=serve_cli)


def serve_cli(args):
    if not args.container:
        args.detach = False
    model = New(args.MODEL, args)
    model.serve(args)


def stop_parser(subparsers):
    parser = subparsers.add_parser("stop", help="stop named container that is running AI Model")
    parser.add_argument("-a", "--all", action="store_true", help="stop all RamaLama containers")
    parser.add_argument("--container", default=False, action="store_false", help=argparse.SUPPRESS)
    parser.add_argument(
        "--ignore", action="store_true", help="ignore errors when specified RamaLama container is missing"
    )
    parser.add_argument("NAME", nargs="?")  # positional argument
    parser.set_defaults(func=stop_container)


def _stop_container(args, name):
    if not name:
        raise IndexError("must specify a container name")
    conman = args.engine
    if conman == "":
        raise IndexError("no container manager (Podman, Docker) found")

    conman_args = [conman, "stop", "-t=0"]
    ignore_stderr = False
    if args.ignore:
        if conman == "podman":
            conman_args += ["--ignore", str(args.ignore)]
        else:
            ignore_stderr = True

    conman_args += [name]
    try:
        run_cmd(conman_args, ignore_stderr=ignore_stderr)
    except subprocess.CalledProcessError:
        if args.ignore and conman == "docker":
            return
        else:
            raise


def stop_container(args):
    if not args.all:
        return _stop_container(args, args.NAME)

    if args.NAME:
        raise IndexError("specifying --all and container name, %s, not allowed" % args.NAME)
    args.ignore = True
    args.format = "{{ .Names }}"
    for i in _list_containers(args):
        _stop_container(args, i)


def version_parser(subparsers):
    parser = subparsers.add_parser("version", help="display version of AI Model")
    # Do not run in a container
    parser.add_argument("--container", default=False, action="store_false", help=argparse.SUPPRESS)
    parser.set_defaults(func=print_version)


def rm_parser(subparsers):
    parser = subparsers.add_parser("rm", help="remove AI Model from local storage")
    parser.add_argument("--container", default=False, action="store_false", help=argparse.SUPPRESS)
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
            for prefix in model_types:
                if model.startswith(prefix + "://"):
                    if not args.ignore:
                        raise e
            try:
                # attempt to remove as a container image
                m = OCI(model, args.engine)
                m.remove(args, ignore_stderr=True)
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

    args.noheading = True
    models = [k['name'] for k in _list_models(args)]
    _rm_model(models, args)


def run_container(args):
    if hasattr(args, "generate") and args.generate:
        return False

    if not args.container:
        if hasattr(args, "name") and args.name:
            raise IndexError("--nocontainer and --name options conflict. --name requires a container.")

        # --nocontainer implies --detach=false
        if hasattr(args, "detach"):
            args.detach = False
        return False

    model = New(args.image, args)
    return model.run_container(args, shortnames)


def New(model, args):
    if model.startswith("huggingface") or model.startswith("hf://"):
        return Huggingface(model)
    if model.startswith("ollama"):
        return Ollama(model)
    if model.startswith("oci://") or model.startswith("docker://"):
        return OCI(model, args.engine)
    if model.startswith("http://") or model.startswith("https://") or model.startswith("file://"):
        return URL(model)

    transport = config.get("transport", "ollama")
    if transport == "huggingface":
        return Huggingface(model)
    if transport == "ollama":
        return Ollama(model)
    if transport == "oci":
        return OCI(model, args.engine)

    raise KeyError(f'transport "{transport}" not supported. Must be oci, huggingface, or ollama.')
