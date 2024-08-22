import os
import re
from ramalama import *
from ramalama.common import run_cmd


def download(ramalama_store, model, directory, filename):
    return run_cmd(["huggingface-cli", "download", directory, filename, "--cache-dir", ramalama_store + "/repos/huggingface/.cache", "--local-dir", ramalama_store + "/repos/huggingface/" + directory])


def try_download(ramalama_store, model, directory, filename):
    proc = download(ramalama_store, model, directory, filename)
    return proc.stdout.decode('utf-8')


def pull(model, ramalama_store):
    model = re.sub(r'^huggingface://', '', model)
    directory, filename = model.rsplit('/', 1)
    gguf_path = try_download(
        ramalama_store, model, directory, filename)
    directory = f"{ramalama_store}/models/huggingface/{directory}"
    os.makedirs(directory, exist_ok=True)
    symlink_path = f"{directory}/{filename}"
    relative_target_path = os.path.relpath(
        gguf_path.rstrip(), start=os.path.dirname(symlink_path))
    if os.path.exists(symlink_path) and os.readlink(symlink_path) == relative_target_path:
        # Symlink is already correct, no need to update it
        return symlink_path

    run_cmd(["ln", "-sf", relative_target_path, symlink_path])

    return symlink_path

def push(store, model, target):
    raise NotImplementedError("ramalama push not implemented for huggingface transport")
