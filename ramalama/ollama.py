import json
import os
import urllib.error
from typing import Optional

from ramalama.common import available, perror
from ramalama.model import Model
from ramalama.model_store.snapshot_file import SnapshotFile, SnapshotFileType
from ramalama.ollama_repo_utils import fetch_manifest_data


def in_existing_cache(model_name, model_tag):
    if not available("ollama"):
        return None
    default_ollama_caches = [
        os.path.join(os.environ['HOME'], '.ollama/models'),
        '/usr/share/ollama/.ollama/models',
        'C:\\Users\\%username%\\.ollama\\models',
    ]

    for cache_dir in default_ollama_caches:
        manifest_path = os.path.join(cache_dir, 'manifests', 'registry.ollama.ai', model_name, model_tag)
        if os.access(manifest_path, os.R_OK):
            with open(manifest_path, 'r') as file:
                manifest_data = json.load(file)
                for layer in manifest_data["layers"]:
                    if layer["mediaType"] == "application/vnd.ollama.image.model":
                        layer_digest = layer["digest"]
                        ollama_digest_path = os.path.join(cache_dir, 'blobs', layer_digest)
                        if os.path.exists(str(ollama_digest_path).replace(':', '-')):
                            return str(ollama_digest_path).replace(':', '-')
    return None


class OllamaRepository:
    REGISTRY_URL = "https://registry.ollama.ai/v2/library"
    ACCEPT = "Accept: application/vnd.docker.distribution.manifest.v2+json"

    FILE_NAME_CONFIG = "config.json"
    FILE_NAME_CHAT_TEMPLATE = "chat_template"

    def __init__(self, name):
        self.name = name
        self.registry_head = f"{OllamaRepository.REGISTRY_URL}/{name}"
        self.blob_url = f"{self.registry_head}/blobs"
        self.headers = {"Accept": OllamaRepository.ACCEPT}

    def fetch_manifest(self, tag: str):
        try:
            return fetch_manifest_data(self.registry_head, tag, OllamaRepository.ACCEPT)
        except urllib.error.HTTPError as e:
            if "Not Found" in e.reason:
                raise KeyError(f"Manifest for {self.name}:{tag} was not found in the Ollama registry")

            err = str(e).strip("'")
            raise KeyError(f"failed to fetch manifest: {err}")

    def get_file_list(self, tag, cached_files, is_model_in_ollama_cache, manifest=None) -> list[SnapshotFile]:
        if manifest is None:
            manifest = self.fetch_manifest(tag)

        files = []
        if self.name not in cached_files and not is_model_in_ollama_cache:
            model = self.model_file(tag, manifest)
            if model is not None:
                files.append(model)
        if OllamaRepository.FILE_NAME_CONFIG not in cached_files:
            files.append(self.config_file(tag, manifest))
        if OllamaRepository.FILE_NAME_CHAT_TEMPLATE not in cached_files:
            chat_template = self.chat_template_file(tag, manifest)
            if chat_template is not None:
                files.append(chat_template)

        return files

    def get_model_hash(self, manifest) -> str:
        for layer in manifest["layers"]:
            layer_digest = layer["digest"]
            if layer["mediaType"] == "application/vnd.ollama.image.model":
                return layer_digest
        return ""

    def model_file(self, tag, manifest=None) -> Optional[SnapshotFile]:
        if manifest is None:
            manifest = self.fetch_manifest(tag)

        model_digest = self.get_model_hash(manifest)
        if model_digest == "":
            return None

        return SnapshotFile(
            url=f"{self.blob_url}/{model_digest}",
            header=self.headers,
            hash=model_digest,
            type=SnapshotFileType.Model,
            name=self.name,
            should_show_progress=True,
            should_verify_checksum=True,
        )

    def config_file(self, tag, manifest=None) -> SnapshotFile:
        if manifest is None:
            manifest = self.fetch_manifest(tag)

        config_hash = manifest["config"]["digest"]

        return SnapshotFile(
            url=f"{self.blob_url}/{config_hash}",
            header=self.headers,
            hash=config_hash,
            type=SnapshotFileType.Other,
            name=OllamaRepository.FILE_NAME_CONFIG,
        )

    def get_chat_template_hash(self, manifest) -> str:
        for layer in manifest["layers"]:
            layer_digest = layer["digest"]
            if layer["mediaType"] == "application/vnd.ollama.image.template":
                return layer_digest
        return ""

    def chat_template_file(self, tag, manifest=None) -> Optional[SnapshotFile]:
        if manifest is None:
            manifest = self.fetch_manifest(tag)

        chat_template_digest = self.get_chat_template_hash(manifest)
        if chat_template_digest == "":
            return None

        return SnapshotFile(
            url=f"{self.blob_url}/{chat_template_digest}",
            header=self.headers,
            hash=chat_template_digest,
            type=SnapshotFileType.ChatTemplate,
            name=OllamaRepository.FILE_NAME_CHAT_TEMPLATE,
        )


class Ollama(Model):
    def __init__(self, model, model_store_path):
        super().__init__(model, model_store_path)

        self.type = "Ollama"

    def pull(self, args):
        name, tag, _ = self.extract_model_identifiers()
        _, cached_files, all = self.model_store.get_cached_files(tag)
        if all:
            if not args.quiet:
                perror(f"Using cached ollama://{name}:{tag} ...")
            return

        ollama_repo = OllamaRepository(self.model_store.model_name)
        manifest = ollama_repo.fetch_manifest(tag)
        ollama_cache_path = in_existing_cache(self.model_name, tag)
        is_model_in_ollama_cache = ollama_cache_path is not None
        files: list[SnapshotFile] = ollama_repo.get_file_list(tag, cached_files, is_model_in_ollama_cache)

        if not args.quiet:
            self.print_pull_message(f"ollama://{name}:{tag}")

        model_hash = ollama_repo.get_model_hash(manifest)
        self.model_store.new_snapshot(tag, model_hash, files)

        # If a model has been downloaded via ollama cli, only create symlink in the snapshots directory
        if is_model_in_ollama_cache:
            if not args.quiet:
                perror(f"Using cached ollama://{name}{tag} ...")
            snapshot_model_path = self.model_store.get_snapshot_file_path(model_hash, self.model_store.model_name)
            os.symlink(ollama_cache_path, snapshot_model_path)
