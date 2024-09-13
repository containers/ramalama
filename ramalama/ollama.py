import os
import subprocess
import json

from ramalama.common import run_cmd, run_curl_cmd
from ramalama.model import Model


def pull_manifest(repos, manifests, accept, registry_head, model_tag):
    os.makedirs(os.path.dirname(manifests), exist_ok=True)
    os.makedirs(os.path.join(repos, "blobs"), exist_ok=True)
    curl_cmd = ["curl", "-f", "-s", "--header", accept, "-o", manifests, f"{registry_head}/manifests/{model_tag}"]
    run_cmd(curl_cmd)


def pull_blob(repos, layer_digest, accept, registry_head, models, model_name, model_tag, symlink_path):
    layer_blob_path = os.path.join(repos, "blobs", layer_digest)
    curl_cmd = [
        "curl",
        "-f",
        "-L",
        "-C",
        "-",
        "--progress-bar",
        "--header",
        accept,
        "-o",
        layer_blob_path,
        f"{registry_head}/blobs/{layer_digest}",
    ]
    run_curl_cmd(curl_cmd, layer_blob_path)
    os.makedirs(models, exist_ok=True)
    relative_target_path = os.path.relpath(layer_blob_path, start=os.path.dirname(symlink_path))
    run_cmd(["ln", "-sf", relative_target_path, symlink_path])


def init_pull(repos, manifests, accept, registry_head, model_name, model_tag, models, symlink_path, model):
    try:
        pull_manifest(repos, manifests, accept, registry_head, model_tag)
        with open(manifests, "r") as f:
            manifest_data = json.load(f)
    except subprocess.CalledProcessError as e:
        if e.returncode == 22:
            raise KeyError((f"{model} not found"))

        raise e

    for layer in manifest_data["layers"]:
        layer_digest = layer["digest"]
        if layer["mediaType"] != "application/vnd.ollama.image.model":
            continue

        pull_blob(repos, layer_digest, accept, registry_head, models, model_name, model_tag, symlink_path)

    return symlink_path


class Ollama(Model):
    def __init__(self, model):
        super().__init__(model.removeprefix("ollama://"))
        self.type = "Ollama"

    def pull(self, args):
        repos = args.store + "/repos/ollama"
        models = args.store + "/models/ollama"
        registry = "https://registry.ollama.ai"
        if "/" in self.model:
            model_full = self.model
            models = os.path.join(models, model_full.rsplit("/", 1)[0])
        else:
            model_full = "library/" + self.model

        accept = "Accept: application/vnd.docker.distribution.manifest.v2+json"
        if ":" in model_full:
            model_name, model_tag = model_full.split(":", 1)
        else:
            model_name = model_full
            model_tag = "latest"

        model_base = os.path.basename(model_name)
        symlink_path = os.path.join(models, f"{model_base}:{model_tag}")
        if os.path.exists(symlink_path):
            return symlink_path

        manifests = os.path.join(repos, "manifests", registry, model_name, model_tag)
        registry_head = f"{registry}/v2/{model_name}"
        return init_pull(
            repos, manifests, accept, registry_head, model_name, model_tag, models, symlink_path, self.model
        )

    def get_symlink_path(self, args):
        models = args.store + "/models/ollama"
        if "/" in self.model:
            model_full = self.model
            models = os.path.join(models, model_full.rsplit("/", 1)[0])
        else:
            model_full = "library/" + self.model

        if ":" in model_full:
            model_name, model_tag = model_full.split(":", 1)
        else:
            model_name = model_full
            model_tag = "latest"

        model_base = os.path.basename(model_name)
        return os.path.join(models, f"{model_base}:{model_tag}")
