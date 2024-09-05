#!/usr/bin/python3

from argparse import ArgumentParser
from pathlib import Path
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time

from ramalama.huggingface import Huggingface
from ramalama.common import in_container, container_manager, exec_cmd
from ramalama.oci import OCI
from ramalama.ollama import Ollama
from ramalama.version import version


def use_container():
    transport = os.getenv("RAMALAMA_IN_CONTAINER", "true")
    return transport.lower() == "true"


def init_cli():
    parser = ArgumentParser(prog='ramalama',
                            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                            description="Simple management tool for working with AI Models.")
    parser.add_argument("--store",
                        default=get_store(),
                        help="store AI Models in the specified directory")
    parser.add_argument("--dryrun",
                        action='store_true',
                        help="show container runtime command without executing it")
    parser.add_argument("--nocontainer",
                        default=not use_container(),
                        action='store_true',
                        help="do not run ramalama in the default container")

    subparsers = parser.add_subparsers(dest='subcommand')
    subparsers.required = True
    list_parser(subparsers)
    login_parser(subparsers)
    logout_parser(subparsers)
    pull_parser(subparsers)
    push_parser(subparsers)
    run_parser(subparsers)
    serve_parser(subparsers)
    version_parser(subparsers)
    # Parse CLI
    args = parser.parse_args()
    # create stores directories
    mkdirs(args.store)
    if run_container(args):
        return

    # Process CLI
    args.func(args)


def login_parser(subparsers):
    parser = subparsers.add_parser('login', help='Login to remote registry')
    # Do not run in a container
    parser.add_argument("--nocontainer",
                        action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument("-p", "--password", dest="password",
                        help="password for registry")
    parser.add_argument("--password-stdin", dest="passwordstdin",
                        action='store_true',
                        help="take the password for registry from stdin")
    parser.add_argument("--token", dest="token",
                        help="token for registry")
    parser.add_argument("-u", "--username", dest="username",
                        help="username for registry")
    parser.add_argument('transport', nargs='?', type=str,
                        default="")  # positional argument
    parser.set_defaults(func=login_cli)


def login_cli(args):
    transport = args.transport
    if transport != "":
        transport = os.getenv("RAMALAMA_TRANSPORT")
    model = New(str(transport))
    return model.login(args)


def logout_parser(subparsers):
    parser = subparsers.add_parser(
        'logout', help='Logout from remote registry')
    # Do not run in a container
    parser.add_argument("--nocontainer",
                        action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument("--token", dest="token",
                        help="Token for registry")
    parser.add_argument('transport', nargs='?', type=str,
                        default="")  # positional argument
    parser.set_defaults(func=logout_cli)


def logout_cli(args):
    transport = args.transport
    if transport != "":
        transport = os.getenv("RAMALAMA_TRANSPORT")
    model = New(str(transport))
    return model.logout(args)


def mkdirs(store):
    # List of directories to create
    directories = [
        'models/huggingface',
        'repos/huggingface',
        'models/oci',
        'repos/oci',
        'models/ollama',
        'repos/ollama'
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
    return sorted(Path().rglob('*'), key=lambda p: os.path.getmtime(p),
                  reverse=True)


def add_list_parser(subparsers, name, func):
    parser = subparsers.add_parser(name, help='List all downloaded AI Models')
    parser.add_argument("-n", "--noheading", dest="noheading",
                        action='store_true',
                        help="do not display heading")
    parser.add_argument("--json", dest="json",
                        action='store_true',
                        help="print using json")
    parser.set_defaults(func=func)


def list_parser(subparsers):
    add_list_parser(subparsers, 'list', list_cli)
    add_list_parser(subparsers, 'ls', list_cli)


def list_cli(args):
    if not args.noheading:
        print(f"{'NAME':<67} {'MODIFIED':<15} {'SIZE':<6}")
    mycwd = os.getcwd()
    os.chdir(f"{args.store}/models/")
    models = []
    for path in list_files_by_modification():
        if path.is_symlink():
            name = str(path).replace('/', '://', 1)
            file_epoch = path.lstat().st_mtime
            diff = int(time.time() - file_epoch)
            modified = human_duration(diff) + " ago"
            size = subprocess.run(["du", "-h", str(path.resolve())],
                                  capture_output=True, text=True).stdout.split()[0]
            if args.json:
                models.append({"name": name, "modified": diff, "size": size})
            else:
                print(f"{name:<67} {modified:<15} {size:<6}")
    os.chdir(mycwd)

    if args.json:
        json_dict = {"models": models}
        print(json.dumps(json_dict))


def pull_parser(subparsers):
    parser = subparsers.add_parser(
        'pull', help='Pull AI model from model registry to local storage')
    parser.add_argument('model')         # positional argument
    parser.set_defaults(func=pull_cli)


def pull_cli(args):
    model = New(args.model)
    matching_files = glob.glob(f"{args.store}/models/*/{model}")
    if matching_files:
        return matching_files[0]

    return model.pull(args)


def push_parser(subparsers):
    parser = subparsers.add_parser(
        'push', help='Push AI Model from local storage to remote model registry')
    parser.add_argument('model')         # positional argument
    parser.add_argument('target')         # positional argument
    parser.set_defaults(func=push_cli)


def push_cli(args):
    model = New(args.model)
    model.push(args)


def run_parser(subparsers):
    parser = subparsers.add_parser(
        'run', help='Run chatbot on specified AI Model')
    parser.add_argument("--prompt", dest="prompt",
                        action='store_true',
                        help="modify chatbot prompt")
    parser.add_argument('model')         # positional argument
    parser.add_argument('args', nargs='*',
                        help='additinal options to pass to the AI Model')
    parser.set_defaults(func=run_cli)


def run_cli(args):
    model = New(args.model)
    model.run(args)


def serve_parser(subparsers):
    parser = subparsers.add_parser(
        'serve', help='Serve REST API on specified AI Model')
    parser.add_argument("--port", default="8080",
                        help="port for AI Model server to listen on")
    parser.add_argument('model')         # positional argument
    parser.set_defaults(func=serve_cli)


def serve_cli(args):
    model = New(args.model)
    model.serve(args)


def version_parser(subparsers):
    parser = subparsers.add_parser(
        'version', help='Display version of AI Model')
    parser.set_defaults(func=version_cli)


def version_cli(args):
    version()


def get_store():
    if os.geteuid() == 0:
        return "/var/lib/ramalama"

    return os.path.expanduser("~/.local/share/ramalama")


def find_working_directory():
    wd = "./ramalama"
    for p in sys.path:
        target = p + "ramalama"
        if os.path.exists(target):
            wd = target
            break

    return wd


def run_container(args):
    if args.nocontainer or in_container() or sys.platform == 'darwin':
        return False

    conman = container_manager()
    if conman == "":
        return False

    home = os.path.expanduser('~')
    wd = find_working_directory()
    conman_args = [conman, "run",
                   "--rm",
                   "-it",
                   "--security-opt=label=disable",
                   f"-v{args.store}:/var/lib/ramalama",
                   f"-v{home}:{home}",
                   "-v/tmp:/tmp",
                   f"-v{sys.argv[0]}:/usr/bin/ramalama:ro",
                   "-e", "RAMALAMA_TRANSPORT",
                   f"-v{wd}:/usr/share/ramalama/ramalama:ro"]

    if hasattr(args, 'port'):
        conman_args += ["-p", f"{args.port}:{args.port}"]

    if os.path.exists("/dev/dri"):
        conman_args += ["--device", "/dev/dri"]

    if os.path.exists("/dev/kfd"):
        conman_args += ["--device", "/dev/kfd"]

    conman_args += ["quay.io/ramalama/ramalama:latest",
                    "/usr/bin/ramalama"]
    conman_args += sys.argv[1:]
    if args.dryrun:
        print(*conman_args)
        return True

    exec_cmd(conman_args)


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
