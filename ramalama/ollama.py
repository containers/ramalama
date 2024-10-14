import os
import urllib.request
import json
from ramalama.common import run_cmd, verify_checksum
from ramalama.model import Model

bar_format = "Pulling {desc}: {percentage:3.0f}% ▕{bar:20}▏ {n_fmt}/{total_fmt} {rate_fmt} {remaining}"


def download_file(url, dest_path, headers=None, show_progress=True):
    try:
        from tqdm import tqdm
    except FileNotFoundError:
        raise NotImplementedError(
            """\
Ollama models requires the tqdm modules.
This module can be installed via PyPi tools like pip, pip3, pipx or via
distribution package managers like dnf or apt. Example:
pip install tqdm
"""
        )

    # Check if partially downloaded file exists
    if os.path.exists(dest_path):
        downloaded_size = os.path.getsize(dest_path)
    else:
        downloaded_size = 0

    request = urllib.request.Request(url, headers=headers or {})
    request.headers["Range"] = f"bytes={downloaded_size}-"  # Set range header

    try:
        with urllib.request.urlopen(request) as response:
            total_size = int(response.headers.get("Content-Length", 0)) + downloaded_size
            chunk_size = 8192  # 8 KB chunks

            with open(dest_path, "ab") as file:
                if show_progress:
                    with tqdm(
                        desc=dest_path[-16:],
                        total=total_size,
                        initial=downloaded_size,
                        unit="B",
                        unit_scale=True,
                        unit_divisor=1024,
                        bar_format=bar_format,
                        ascii=True,
                    ) as progress_bar:
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break
                            file.write(chunk)
                            progress_bar.update(len(chunk))
                else:
                    # Download file without showing progress
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        file.write(chunk)
    except urllib.error.HTTPError as e:
        if e.code == 416:
            if show_progress:
                # If we get a 416 error, it means the file is fully downloaded
                print(f"File {url} already fully downloaded.")
        else:
            raise e


def pull_manifest(repos, manifests, accept, registry_head, model_tag):
    os.makedirs(os.path.dirname(manifests), exist_ok=True)
    os.makedirs(os.path.join(repos, "blobs"), exist_ok=True)
    url = f"{registry_head}/manifests/{model_tag}"
    headers = {"Accept": accept}

    # Attempt to redownload the manifest if already exists,
    # otherwise json.JSONDecodeError exception is thrown when reading the manifest
    if os.path.exists(manifests):
        os.remove(manifests)

    download_file(url, manifests, headers=headers, show_progress=False)


def pull_config_blob(repos, accept, registry_head, manifest_data):
    cfg_hash = manifest_data["config"]["digest"]
    config_blob_path = os.path.join(repos, "blobs", cfg_hash)
    url = f"{registry_head}/blobs/{cfg_hash}"
    headers = {"Accept": accept}
    download_file(url, config_blob_path, headers=headers, show_progress=False)


def pull_blob(repos, layer_digest, accept, registry_head, models, model_name, model_tag, symlink_path):
    layer_blob_path = os.path.join(repos, "blobs", layer_digest)
    url = f"{registry_head}/blobs/{layer_digest}"
    headers = {"Accept": accept}
    download_file(url, layer_blob_path, headers=headers, show_progress=True)

    # Verify checksum after downloading the blob
    if not verify_checksum(layer_blob_path):
        print(f"Checksum mismatch for blob {layer_blob_path}, retrying download...")
        os.remove(layer_blob_path)
        download_file(url, layer_blob_path, headers=headers, show_progress=True)
        if not verify_checksum(layer_blob_path):
            raise ValueError(f"Checksum verification failed for blob {layer_blob_path}")

    os.makedirs(models, exist_ok=True)
    relative_target_path = os.path.relpath(layer_blob_path, start=os.path.dirname(symlink_path))
    run_cmd(["ln", "-sf", relative_target_path, symlink_path])


def init_pull(repos, manifests, accept, registry_head, model_name, model_tag, models, symlink_path, model):
    try:
        pull_manifest(repos, manifests, accept, registry_head, model_tag)
        with open(manifests, "r") as f:
            manifest_data = json.load(f)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise KeyError(f"{model} not found")
        raise e
    # This exception block acts as a safety-net to redownload the manifests if corrupted.
    except json.JSONDecodeError:
        print(f"Error: Failed to parse JSON in {manifests}. File might be corrupted or incomplete.")
        print("Attempting to redownload the manifest file...")
        os.remove(manifests)
        pull_manifest(repos, manifests, accept, registry_head, model_tag)
        with open(manifests, "r") as f:
            manifest_data = json.load(f)

    pull_config_blob(repos, accept, registry_head, manifest_data)
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

    def _local(self, args):
        models = args.store + "/models/ollama"
        if "/" in self.model:
            model_full = self.model
            self._models = os.path.join(models, model_full.rsplit("/", 1)[0])
        else:
            model_full = "library/" + self.model

        if ":" in model_full:
            model_name, model_tag = model_full.split(":", 1)
        else:
            model_name = model_full
            model_tag = "latest"

        model_base = os.path.basename(model_name)
        symlink_path = os.path.join(models, f"{model_base}:{model_tag}")
        return symlink_path, models, model_base, model_name, model_tag

    def path(self, args):
        symlink_path, _, _, _, _ = self._local(args)
        if not os.path.exists(symlink_path):
            raise KeyError(f"{args.Model} does not exist")

        return symlink_path

    def pull(self, args):
        repos = args.store + "/repos/ollama"
        symlink_path, models, model_base, model_name, model_tag = self._local(args)
        if os.path.exists(symlink_path):
            return symlink_path

        registry = "https://registry.ollama.ai"
        accept = "Accept: application/vnd.docker.distribution.manifest.v2+json"
        manifests = os.path.join(repos, "manifests", registry, model_name, model_tag)
        registry_head = f"{registry}/v2/{model_name}"
        return init_pull(
            repos, manifests, accept, registry_head, model_name, model_tag, models, symlink_path, self.model
        )

    def symlink_path(self, args):
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
