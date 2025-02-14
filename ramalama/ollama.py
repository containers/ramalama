import os
import urllib.request
import json
from ramalama.common import run_cmd, available
from ramalama.model import Model, rm_until_substring
from ramalama.model_store import ModelRegistry, SnapshotFile


def fetch_manifest_data(registry_head, model_tag, accept):
    url = f"{registry_head}/manifests/{model_tag}"
    headers = {"Accept": accept}

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request) as response:
        manifest_data = json.load(response)
    return manifest_data

def in_existing_cache(model_name, model_tag):
    if not available("ollama"):
        return None
    default_ollama_caches = [
        os.path.join(os.environ['HOME'], '.ollama/models'),
        '/usr/share/ollama/.ollama/models',
        f'C:\\Users\\{os.getlogin()}\\.ollama\\models',
    ]

    for cache_dir in default_ollama_caches:
        manifest_path = os.path.join(
            cache_dir, 'manifests', 'registry.ollama.ai', model_name, model_tag
        )
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as file:
                manifest_data = json.load(file)
                for layer in manifest_data["layers"]:
                    if layer["mediaType"] == "application/vnd.ollama.image.model":
                        layer_digest = layer["digest"]
                        ollama_digest_path = os.path.join(cache_dir, 'blobs', layer_digest)
                        if os.path.exists(str(ollama_digest_path).replace(':', '-')):
                            return str(ollama_digest_path).replace(':', '-')
    return None

class Ollama(Model):
    def __init__(self, model, store_path=""):
        model = rm_until_substring(model, "ollama.com/library/")
        model = rm_until_substring(model, "://")

        super().__init__(model, store_path, ModelRegistry.OLLAMA)

    def pull(self, debug = False):
        hash, cached_files, all = self.store.get_cached_files(self.model_tag)
        if all:
            return self.store.get_snapshot_file_path(hash, self.filename)

        registry = "https://registry.ollama.ai/v2/library"
        accept = "Accept: application/vnd.docker.distribution.manifest.v2+json"
        registry_head = f"{registry}/{self.model}"

        try:
            manifest_data = fetch_manifest_data(registry_head, self.model_tag, accept)
        except urllib.error.HTTPError as e:
            if "Not Found" in e.reason:
                raise KeyError(f"Manifest for {self.model} was not found in the Ollama registry")
            raise KeyError(f"failed to fetch manifest: " + str(e).strip("'"))

        model_hash = manifest_data["config"]["digest"]
        model_digest = ""
        chat_template_digest = ""
        for layer in manifest_data["layers"]:
            layer_digest = layer["digest"]
            if layer["mediaType"] == "application/vnd.ollama.image.model":
                model_digest = layer_digest
            elif layer["mediaType"] == "application/vnd.ollama.image.template":
                chat_template_digest = layer_digest

        files: list[SnapshotFile] = []
        model_file_name = self.store.model_name
        config_file_name = "config.json"
        chat_template_file_name = "chat_template"
        ollama_cache_path = in_existing_cache(self.model, self.model_tag)

        blob_url = f"{registry_head}/blobs"
        headers = {"Accept": accept}

        if (
            model_digest != ""
            and model_file_name not in cached_files
            and ollama_cache_path is None
        ):
            files.append(
                SnapshotFile(
                    url=f"{blob_url}/{model_digest}",
                    header=headers,
                    hash=model_digest,
                    name=model_file_name,
                    should_show_progress=True,
                    should_verify_checksum=True,
                )
            )
        if config_file_name not in cached_files:
            files.append(
                SnapshotFile(
                    url=f"{blob_url}/{model_hash}",
                    header=headers,
                    hash=model_hash,
                    name=config_file_name,
                    should_show_progress=False,
                    should_verify_checksum=False,
                )
            )
        if chat_template_digest != "" and chat_template_file_name not in cached_files:
            files.append(
                SnapshotFile(
                    url=f"{blob_url}/{chat_template_digest}",
                    header=headers,
                    hash=chat_template_digest,
                    name=chat_template_file_name,
                    should_show_progress=True,
                    should_verify_checksum=True,
                )
            )

        try:
            self.store.new_snapshot(self.model_tag, model_hash, files)
        except urllib.error.HTTPError as e:
            if "Not Found" in e.reason:
                raise KeyError(f"{self.model} was not found in the Ollama registry")
            raise KeyError(f"failed to pull: " + str(e).strip("'"))

        # If a model has been downloaded via ollama cli, only create symlink in the snapshots directory
        if ollama_cache_path is not None:
            snapshot_model_path = self.store.get_snapshot_file_path(model_hash, model_file_name)
            os.symlink(ollama_cache_path, snapshot_model_path)

        return self.store.get_snapshot_file_path(model_hash, model_file_name)
