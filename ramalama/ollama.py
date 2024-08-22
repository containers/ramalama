import os
import re
import subprocess
import json

from ramalama.common import exec_cmd, run_cmd, run_curl_cmd, perror


def pull_manifest(repos, manifests, accept, registry_head, model_tag):
    os.makedirs(os.path.dirname(manifests), exist_ok=True)
    os.makedirs(os.path.join(repos, "blobs"), exist_ok=True)
    curl_cmd = [
        "curl", "-f", "-s", "--header", accept,
        "-o", manifests,
        f"{registry_head}/manifests/{model_tag}"
    ]
    run_cmd(curl_cmd)


def pull_config_blob(repos, accept, registry_head, manifest_data):
    cfg_hash = manifest_data["config"]["digest"]
    config_blob_path = os.path.join(repos, "blobs", cfg_hash)
    curl_cmd = [
        "curl", "-f", "-s", "-L", "-C", "-", "--header", accept,
        "-o", config_blob_path,
        f"{registry_head}/blobs/{cfg_hash}"
    ]
    run_curl_cmd(curl_cmd, config_blob_path)


def pull_blob(repos, layer_digest, accept, registry_head, models, model_name, model_tag, symlink_path):
    layer_blob_path = os.path.join(repos, "blobs", layer_digest)
    curl_cmd = ["curl", "-f", "-L", "-C", "-", "--progress-bar", "--header",
                accept, "-o", layer_blob_path,
                f"{registry_head}/blobs/{layer_digest}"]
    run_curl_cmd(curl_cmd, layer_blob_path)
    os.makedirs(models, exist_ok=True)
    relative_target_path = os.path.relpath(
        layer_blob_path, start=os.path.dirname(symlink_path))
    run_cmd(["ln", "-sf", relative_target_path, symlink_path])


def pull(model, store):
    model = re.sub(r'^ollama://', '', model)
    repos = store + "/repos/ollama"
    models = store + "/models/ollama"
    registry = "https://registry.ollama.ai"
    if '/' in model:
        model_full = model
    else:
        model_full = "library/" + model

    accept = "Accept: application/vnd.docker.distribution.manifest.v2+json"
    if ':' in model_full:
        model_name, model_tag = model_full.split(':', 1)
    else:
        model_name = model_full
        model_tag = "latest"

    model_base = os.path.basename(model_name)
    symlink_path = os.path.join(models, f"{model_base}:{model_tag}")
    if os.path.exists(symlink_path):
        return symlink_path

    manifests = os.path.join(repos, "manifests",
                             registry, model_name, model_tag)
    registry_head = f"{registry}/v2/{model_name}"
    return init_pull(repos, manifests, accept, registry_head, model_name, model_tag, models, symlink_path, model)


def init_pull(repos, manifests, accept, registry_head, model_name, model_tag, models, symlink_path, model):
    try:
        pull_manifest(repos, manifests,
                      accept, registry_head, model_tag)
        with open(manifests, 'r') as f:
            manifest_data = json.load(f)
    except subprocess.CalledProcessError as e:
        if e.returncode == 22:
            raise KeyError((f"{model}:{model_tag} not found"))

        raise e

    pull_config_blob(repos, accept,
                     registry_head, manifest_data)
    for layer in manifest_data["layers"]:
        layer_digest = layer["digest"]
        if layer["mediaType"] != 'application/vnd.ollama.image.model':
            continue

        pull_blob(repos, layer_digest, accept,
                  registry_head, models, model_name, model_tag,
                  symlink_path)

    return symlink_path
