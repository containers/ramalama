#!/usr/bin/python3

from argparse import ArgumentParser
from pathlib import Path
import argparse
import glob
import json
import os
import random
import string
import subprocess
import sys
import time
import configparser

from ramalama.huggingface import Huggingface
from ramalama.common import in_container, container_manager, exec_cmd, run_cmd
from ramalama.oci import OCI
from ramalama.ollama import Ollama
from ramalama.version import version


class HelpException(Exception):
    pass


def use_container():
    transport = os.getenv("RAMALAMA_IN_CONTAINER", "true")
    return transport.lower() == "true"


def init_cli():
    parser = ArgumentParser(
        prog="ramalama",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Simple management tool for working with AI Models.",
    )
    parser.add_argument("--store", default=get_store(), help="store AI Models in the specified directory")
    parser.add_argument("--dryrun", action="store_true", help="show container runtime command without executing it")
    parser.add_argument(
        "--nocontainer",
        default=not use_container(),
        action="store_true",
        help="do not run ramalama in the default container",
    )

    parser.add_argument("-v", dest="version", action="store_true", help="show ramalama version")

    subparsers = parser.add_subparsers(dest="subcommand")
    subparsers.required = False

    help_parser(subparsers)
    containers_parser(subparsers)
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
    # Parse CLI
    args = parser.parse_args()
    if args.version:
        return version(args)
    # create stores directories
    mkdirs(args.store)
    if hasattr(args, "MODEL"):
        resolved_model = resolve_shortname(args.MODEL)
        if resolved_model:
            args.UNRESOLVED_MODEL = args.MODEL
            args.MODEL = resolved_model

    if run_container(args):
        return

    # Process CLI
    try:
        args.func(args)
    except HelpException:
        parser.print_help()
    except AttributeError as e:
        print(e)
        parser.print_usage()
        print("ramalama: requires a subcommand")


def login_parser(subparsers):
    parser = subparsers.add_parser("login", help="Login to remote registry")
    # Do not run in a container
    parser.add_argument("--nocontainer", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("-p", "--password", dest="password", help="password for registry")
    parser.add_argument(
        "--password-stdin", dest="passwordstdin", action="store_true", help="take the password for registry from stdin"
    )
    parser.add_argument("--token", dest="token", help="token for registry")
    parser.add_argument("-u", "--username", dest="username", help="username for registry")
    parser.add_argument("TRANSPORT", nargs="?", type=str, default="")  # positional argument
    parser.set_defaults(func=login_cli)


def login_cli(args):
    transport = args.TRANSPORT
    if transport != "":
        transport = os.getenv("RAMALAMA_TRANSPORT")
    model = New(str(transport))
    return model.login(args)


def logout_parser(subparsers):
    parser = subparsers.add_parser("logout", help="Logout from remote registry")
    # Do not run in a container
    parser.add_argument("--nocontainer", default=True, action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--token", help="Token for registry")
    parser.add_argument("TRANSPORT", nargs="?", type=str, default="")  # positional argument
    parser.add_argument("TRANSPORT", nargs="?", type=str, default="")  # positional argument
    parser.set_defaults(func=logout_cli)


def logout_cli(args):
    transport = args.TRANSPORT
    if transport != "":
        transport = os.getenv("RAMALAMA_TRANSPORT")
    model = New(str(transport))
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
    return sorted(Path().rglob("*"), key=lambda p: os.path.getmtime(p), reverse=True)


def containers_parser(subparsers):
    parser = subparsers.add_parser("containers", aliases=["ps"], help="List all ramalama containers")
    parser.add_argument("--format", help="pretty-print containers to JSON or using a Go template")
    parser.add_argument("-n", "--noheading", dest="noheading", action="store_true", help="do not display heading")
    parser.add_argument("--nocontainer", default=True, action="store_true", help=argparse.SUPPRESS)
    parser.set_defaults(func=list_containers)


def _list_containers(args):
    conman = container_manager()
    if conman == "":
        raise IndexError("no container manager (Podman, Docker) found")

    conman_args = [conman, "ps", "-a", "--filter", "label=RAMALAMA container"]
    if args.noheading:
        conman_args += ["--noheading"]

    if args.format:
        conman_args += [f"--format={args.format}"]

    output = run_cmd(conman_args).stdout.decode("utf-8").strip()
    if output == "":
        return []
    return output.split("\n")


def list_containers(args):
    if len(_list_containers(args)) == 0:
        return
    print("\n".join(_list_containers(args)))


def list_parser(subparsers):
    parser = subparsers.add_parser("list", aliases=["ls"], help="List all downloaded AI Models")
    parser.add_argument("-n", "--noheading", dest="noheading", action="store_true", help="do not display heading")
    parser.add_argument("--json", dest="json", action="store_true", help="print using json")
    parser.set_defaults(func=list_cli)


def list_cli(args):
    mycwd = os.getcwd()
    os.chdir(f"{args.store}/models/")
    models = []

    # Collect model data
    for path in list_files_by_modification():
        if path.is_symlink():
            name = str(path).replace("/", "://", 1)
            file_epoch = path.lstat().st_mtime
            diff = int(time.time() - file_epoch)
            modified = human_duration(diff) + " ago"
            size = subprocess.run(["du", "-h", str(path.resolve())], capture_output=True, text=True).stdout.split()[0]

            # Store data for later use
            models.append({"name": name, "modified": modified, "size": size})

    os.chdir(mycwd)

    # If JSON output is requested
    if args.json:
        print(json.dumps(models))
        return

    # Calculate maximum width for each column
    name_width = len("NAME")
    modified_width = len("MODIFIED")
    size_width = len("SIZE")
    for model in models:
        name_width = max(name_width, len(model["name"]))
        modified_width = max(modified_width, len(model["modified"]))
        size_width = max(size_width, len(model["size"]))

    if not args.noheading and not args.json:
        print(f"{'NAME':<{name_width}} {'MODIFIED':<{modified_width}} {'SIZE':<{size_width}}")

    for model in models:
        print(f"{model['name']:<{name_width}} {model['modified']:<{modified_width}} {model['size']:<{size_width}}")


def help_parser(subparsers):
    parser = subparsers.add_parser("help", help="Help about any command")
    # Do not run in a container
    parser.add_argument("--nocontainer", default=True, action="store_true", help=argparse.SUPPRESS)
    parser.set_defaults(func=help_cli)


def help_cli(args):
    raise HelpException()


def pull_parser(subparsers):
    parser = subparsers.add_parser("pull", help="Pull AI Model from model registry to local storage")
    parser.add_argument("MODEL")  # positional argument
    parser.set_defaults(func=pull_cli)


def pull_cli(args):
    model = New(args.MODEL)
    matching_files = glob.glob(f"{args.store}/models/*/{model}")
    if matching_files:
        return matching_files[0]

    return model.pull(args)


def push_parser(subparsers):
    parser = subparsers.add_parser("push", help="Push AI model from local storage to remote registry")
    parser.add_argument("MODEL")  # positional argument
    parser.add_argument("TARGET")  # positional argument
    parser.set_defaults(func=push_cli)


def push_cli(args):
    model = New(args.MODEL)
    model.push(args)


def _name():
    return "ramalama_" + "".join(random.choices(string.ascii_letters + string.digits, k=10))


def run_parser(subparsers):
    parser = subparsers.add_parser("run", help="Run specified AI Model as a chatbot")
    parser.add_argument("--prompt", dest="prompt", action="store_true", help="modify chatbot prompt")
    parser.add_argument("-n", "--name", dest="name", help="name of container in which the model will be run")
    parser.add_argument("MODEL")  # positional argument
    parser.add_argument("ARGS", nargs="*", help="additional options to pass to the AI Model")
    parser.set_defaults(func=run_cli)


def run_cli(args):
    model = New(args.MODEL)
    model.run(args)


def serve_parser(subparsers):
    parser = subparsers.add_parser("serve", help="Serve REST API on specified AI Model")
    parser.add_argument("-d", "--detach", dest="detach", action="store_true", help="run the container in detached mode")
    parser.add_argument("-n", "--name", dest="name", help="name of container in which the model will be run")
    parser.add_argument("-p", "--port", default="8080", help="port for AI Model server to listen on")
    parser.add_argument("MODEL")  # positional argument
    parser.set_defaults(func=serve_cli)


def serve_cli(args):
    model = New(args.MODEL)
    model.serve(args)


def stop_cli(args):
    model = New(args.MODEL)
    model.stop(args)


def stop_parser(subparsers):
    parser = subparsers.add_parser("stop", help="Stop named container that is running AI Model")
    parser.add_argument("--nocontainer", default=True, action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("-a", "--all", action="store_true", help="Stop all ramalama containers")
    parser.add_argument("NAME", nargs="?")  # positional argument
    parser.set_defaults(func=stop_container)


def _stop_container(name):
    conman = container_manager()
    if conman == "":
        raise IndexError("no container manager (Podman, Docker) found")

    conman_args = [
        conman,
        "stop",
        "-t=0",
        name,
    ]

    run_cmd(conman_args)


def stop_container(args):
    if not args.all:
        return _stop_container(args.NAME)

    if args.NAME == "":
        raise IndexError("can not specify --all as well NAME")

    args.noheading = True
    args.format = "{{ .Names }}"
    for i in _list_containers(args):
        _stop_container(i)


def version_parser(subparsers):
    parser = subparsers.add_parser("version", help="Display version of AI Model")
    # Do not run in a container
    parser.add_argument("--nocontainer", default=True, action="store_true", help=argparse.SUPPRESS)
    parser.set_defaults(func=version)


def rm_parser(subparsers):
    parser = subparsers.add_parser("rm", help="Remove AI Model from local storage")
    parser.add_argument("MODEL")
    parser.set_defaults(func=rm_cli)


def rm_cli(args):
    model = New(args.MODEL)
    model.remove(args)


def get_store():
    if os.geteuid() == 0:
        return "/var/lib/ramalama"

    return os.path.expanduser("~/.local/share/ramalama")


def find_working_directory():
    if os.path.exists("./ramalama"):
        return "./ramalama"

    for p in sys.path:
        p = os.path.join(p, "ramalama")
        if os.path.exists(p):
            return p

    return ""


def run_container(args):
    if args.nocontainer:
        if hasattr(args, "name") and args.name != "":
            raise IndexError("--nocontainer and --name options conflict. --name requires a container.")

        if hasattr(args, "detach") and args.detach:
            raise IndexError(
                "--nocontainer and --detach options conflict. --detach requires the model to be run in a container."
            )

    if args.nocontainer or in_container() or sys.platform == "darwin":
        return False

    name = _name()
    if hasattr(args, "name") and args.name is not None:
        name = args.name

    conman = container_manager()
    if conman == "":
        return False

    home = os.path.expanduser("~")
    wd = find_working_directory()
    conman_args = [
        conman,
        "run",
        "--rm",
        "-it",
        "--label=RAMALAMA container",
        "--security-opt=label=disable",
        "-v/tmp:/tmp",
        "-e",
        "RAMALAMA_TRANSPORT",
        "--name",
        name,
        f"-v{args.store}:/var/lib/ramalama",
        f"-v{home}:{home}",
        f"-v{sys.argv[0]}:/usr/bin/ramalama:ro",
        f"-v{wd}:/usr/share/ramalama/ramalama:ro",
    ]

    if hasattr(args, "detach") and args.detach:
        conman_args += ["-d"]

    if hasattr(args, "port"):
        conman_args += ["-p", f"{args.port}:{args.port}"]

    if os.path.exists("/dev/dri"):
        conman_args += ["--device", "/dev/dri"]

    if os.path.exists("/dev/kfd"):
        conman_args += ["--device", "/dev/kfd"]

    conman_args += ["quay.io/ramalama/ramalama:latest", "/usr/bin/ramalama"]
    conman_args += sys.argv[1:]
    if hasattr(args, "UNRESOLVED_MODEL"):
        index = conman_args.index(args.UNRESOLVED_MODEL)
        conman_args[index] = args.MODEL

    if args.dryrun:
        print(*conman_args)
        return True

    exec_cmd(conman_args)


def strip_quotes(s):
    return s.strip("'\"")


def remove_quotes(data):
    # Remove leading and trailing quotes from keys and values
    cleaned_dict = {strip_quotes(key): strip_quotes(value) for key, value in data.items()}

    return cleaned_dict


def load_shortnames():
    config = configparser.ConfigParser()
    aliases = {}
    file_paths = [
        "usr/share/ramalama/aliases.conf",  # for development
        "/usr/share/ramalama/aliases.conf",
        "/etc/ramalama/aliases.conf",
        os.path.expanduser("~/.config/ramalama/aliases.conf"),
    ]

    for file_path in file_paths:
        config.read(file_path)
        if "aliases" in config:
            aliases.update(config["aliases"])

    return remove_quotes(aliases)


def resolve_shortname(model):
    shortnames = load_shortnames()
    return shortnames.get(model)


def New(model):
    if model.startswith("huggingface"):
        return Huggingface(model)
    if model.startswith("ollama"):
        return Ollama(model)
    if model.startswith("oci") | model.startswith("docker"):
        return OCI(model)

    transport = os.getenv("RAMALAMA_TRANSPORT")
    if transport == "huggingface":
        return Huggingface(model)
    if transport == "ollama":
        return Ollama(model)
    if transport == "oci":
        return OCI(model)

    return Ollama(model)
