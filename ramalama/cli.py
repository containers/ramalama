#!/usr/bin/python3

import glob
import json
import logging
import os
import re
import subprocess
import sys
import time
from ramalama.common import exec_cmd
import ramalama.ollama as ollama
import ramalama.oci as oci
import ramalama.huggingface as huggingface
from pathlib import Path


def usage(exit=0):
    print("Usage:")
    print(f"  {os.path.basename(__file__)} COMMAND")
    print()
    print("Commands:")
    print("  list              List models")
    print("  login             Login to specified registry")
    print("  logout            Logout from the specified registry")
    print("  pull MODEL        Pull a model")
    print("  push MODEL TARGET Push a model to target")
    print("  run MODEL         Run a model")
    print("  serve MODEL       Serve a model")
    sys.exit(exit)


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


def login_cli(store, args, port):
    transport = os.getenv("RAMALAMA_TRANSPORT")

    if len(args) > 0:
        transport = args[-1]
        del args[-1]

    if transport == "huggingface":
        return huggingface.login(args)
    if transport == "ollama":
        return ollama.login(args)

    return oci.login(transport, args)


def logout_cli(store, args, port):
    transport = os.getenv("RAMALAMA_TRANSPORT")

    if len(args) > 0:
        transport = args[-1]
        del args[-1]

    if transport == "huggingface":
        return huggingface.logout(args)
    if transport == "ollama":
        return ollama.logout(args)

    return oci.logout(transport, args)


def list_cli(store, args, port):
    if len(args) > 0:
        usage(1)
    print(f"{'NAME':<67} {'MODIFIED':<15} {'SIZE':<6}")
    mycwd = os.getcwd()
    os.chdir(f"{store}/models/")
    for path in list_files_by_modification():
        if path.is_symlink():
            name = str(path).replace('/', '://', 1)
            file_epoch = path.lstat().st_mtime
            diff = int(time.time() - file_epoch)
            modified = human_duration(diff) + " ago"
            size = subprocess.run(["du", "-h", str(path.resolve())],
                                  capture_output=True, text=True).stdout.split()[0]
            print(f"{name:<67} {modified:<15} {size:<6}")
    os.chdir(mycwd)


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


def list_cli(store, args, port):
    if len(args) > 0:
        usage()
    print(f"{'NAME':<67} {'MODIFIED':<15} {'SIZE':<6}")
    mycwd = os.getcwd()
    os.chdir(f"{store}/models/")
    for path in list_files_by_modification():
        if path.is_symlink():
            name = str(path).replace('/', '://', 1)
            file_epoch = path.lstat().st_mtime
            diff = int(time.time() - file_epoch)
            modified = human_duration(diff) + " ago"
            size = subprocess.run(["du", "-h", str(path.resolve())],
                                  capture_output=True, text=True).stdout.split()[0]
            print(f"{name:<67} {modified:<15} {size:<6}")
    os.chdir(mycwd)


def pull_cli(store, args, port):
    if len(args) < 1:
        usage(1)

    model = args.pop(0)
    matching_files = glob.glob(f"{store}/models/*/{model}")
    if matching_files:
        return matching_files[0]

    if model.startswith("huggingface://"):
        return huggingface.pull(model, store)
    if model.startswith("oci://"):
        return oci.pull(model, store)
    if model.startswith("ollama://"):
        return ollama.pull(model, store)

    transport = os.getenv("RAMALAMA_TRANSPORT")
    if transport == "huggingface":
        return huggingface.pull(model, store)
    if transport == "oci":
        return oci.pull(model, store)
    if transport == "ollama":
        return ollama.pull(model, store)

    ollama.pull(model, store)


def push_cli(store, args, port):
    if len(args) < 2:
        usage(1)

    model = args.pop(0)
    target = args.pop(0)
    if model.startswith("oci://"):
        return oci.push(store, model, target)
    if model.startswith("huggingface://"):
        return huggingface.push(store, model, target)
    if model.startswith("ollama://"):
        return ollama.push(store, model, target)

    raise KeyError(
        f"Unsupported transport model must have ollama://, oci://, or huggingface:// prefix: {model}")


def run_cli(store, args, port):
    if len(args) < 1:
        usage(1)

    symlink_path = pull_cli(store, args, port)
    exec_cmd(["llama-cli", "-m",
              symlink_path, "--log-disable", "--instruct"])


def serve_cli(store, args, port):
    if len(args) < 1:
        usage(1)

    symlink_path = pull_cli(store, args, port)
    exec_cmd(["llama-server", "--port", port, "-m", symlink_path])


def get_store():
    if os.geteuid() == 0:
        return "/var/lib/ramalama"

    return os.path.expanduser("~/.local/share/ramalama")


def create_store():
    store = get_store()
    mkdirs(store)
    return store


funcDict = {}
funcDict["list"] = list_cli
funcDict["login"] = login_cli
funcDict["logout"] = logout_cli
funcDict["ls"] = list_cli
funcDict["pull"] = pull_cli
funcDict["push"] = push_cli
funcDict["run"] = run_cli
funcDict["serve"] = serve_cli
