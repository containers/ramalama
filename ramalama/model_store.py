import os
import urllib
from enum import StrEnum
from pathlib import Path
from typing import Dict, Tuple

from ramalama.common import download_file, verify_checksum


class ModelRegistry(StrEnum):
    HUGGINGFACE = "huggingface"
    OLLAMA = "ollama"
    OCI = "oci"
    URL = "url"


class SnapshotFile:

    def __init__(
        self,
        url: str,
        header: Dict,
        hash: str,
        name: str,
        should_show_progress: bool = False,
        should_verify_checksum: bool = False,
        required: bool = True,
    ):
        self.url: str = url
        self.header: Dict = header
        self.hash: str = hash
        self.name: str = name
        self.should_show_progress: bool = should_show_progress
        self.should_verify_checksum: bool = should_verify_checksum
        self.required: bool = required

    def download(self, blob_file_path: str, snapshot_dir: str) -> str:
        download_file(
            url=self.url,
            headers=self.header,
            dest_path=blob_file_path,
            show_progress=self.should_show_progress,
        )
        return os.path.relpath(blob_file_path, start=snapshot_dir)


class RefFile:

    def __init__(self):
        self.hash: str = ""
        self.filenames: list[str] = []

    def from_path(path: str) -> "RefFile":
        ref_file = RefFile()
        with open(path, "r") as file:
            ref_file.hash = file.readline().strip()
            filename = file.readline().strip()
            while filename != "":
                ref_file.filenames.append(filename)
                filename = file.readline().strip()
        return ref_file


class ModelStore:

    def __init__(
        self,
        base_path: Path,
        model_name: str,
        model_organization: str,
        model_registry: ModelRegistry,
    ):
        self._store_base_path = os.path.join(base_path, "store")
        self._model_name = model_name
        self._model_organization = model_organization
        self._model_registry = model_registry

    @property
    def store_path(self) -> str:
        return self._store_base_path

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_organization(self) -> str:
        return self._model_organization if self._model_organization != "" else self._model_name

    @property
    def model_registry(self) -> ModelRegistry:
        return self._model_registry

    @property
    def model_base_directory(self) -> str:
        return os.path.join(self.store_path, self.model_registry, self.model_organization)

    @property
    def blob_directory(self) -> str:
        return os.path.join(self.model_base_directory, "blobs")

    @property
    def ref_directory(self) -> str:
        return os.path.join(self.model_base_directory, "refs")

    @property
    def snapshot_directory(self) -> str:
        return os.path.join(self.model_base_directory, "snapshots")

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        return filename.replace(":", "-")

    def get_ref_file_path(self, model_tag: str) -> str:
        return os.path.join(self.ref_directory, model_tag)

    def get_snapshot_directory(self, hash: str) -> str:
        return os.path.join(self.snapshot_directory, ModelStore.sanitize_filename(hash))

    def get_blob_file_path(self, hash: str) -> str:
        return os.path.join(self.blob_directory, ModelStore.sanitize_filename(hash))

    def get_snapshot_file_path(self, hash: str, filename: str) -> str:
        return os.path.join(self.get_snapshot_directory(ModelStore.sanitize_filename(hash)), filename)

    def resolve_model_directory(self, model_tag: str) -> str:
        ref_file_path = self.get_ref_file_path(model_tag)
        if not self.exists(ref_file_path):
            return ""

        ref_file = RefFile(ref_file_path)
        return self.get_snapshot_directory(ref_file.hash)

    def ensure_directory_setup(self) -> None:
        os.makedirs(self.blob_directory, exist_ok=True)
        os.makedirs(self.ref_directory, exist_ok=True)
        os.makedirs(self.snapshot_directory, exist_ok=True)

    def exists(self, model_tag: str) -> bool:
        return os.path.exists(self.get_ref_file_path(model_tag))

    def get_cached_files(self, model_tag: str) -> Tuple[str, list[str], bool]:
        cached_files = []

        ref_file_path = self.get_ref_file_path(model_tag)
        if not self.exists(ref_file_path):
            return ("", cached_files, False)

        ref_file: RefFile = RefFile.from_path(ref_file_path)
        for file in ref_file.filenames:
            path = self.get_snapshot_file_path(ref_file.hash, file)
            if os.path.exists(path):
                cached_files.append(file)

        return (ref_file.hash, cached_files, len(cached_files) == len(ref_file.filenames))

    def prepare_new_snapshot(self, model_tag: str, snapshot_hash: str, snapshot_files: list[SnapshotFile]):
        self.ensure_directory_setup()

        ref_file = self.get_ref_file_path(model_tag)
        if not os.path.exists(ref_file):
            with open(ref_file, "w") as ref_file:
                ref_file.write(f"{snapshot_hash}")
                for file in snapshot_files:
                    ref_file.write(f"\n{file.name}")

                ref_file.flush()

        snapshot_directory = self.get_snapshot_directory(snapshot_hash)
        os.makedirs(snapshot_directory, exist_ok=True)

    # TODO: implement - iterating over all symlinks in snapshot dir, check valid
    def verify_snapshot(self):
        pass

    def new_snapshot(self, model_tag: str, snapshot_hash: str, snapshot_files: list[SnapshotFile]):
        snapshot_hash = self.sanitize_filename(snapshot_hash)
        self.prepare_new_snapshot(model_tag, snapshot_hash, snapshot_files)

        for file in snapshot_files:
            dest_path = self.get_blob_file_path(file.hash)
            blob_relative_path = ""
            try:
                blob_relative_path = file.download(dest_path, self.get_snapshot_directory(snapshot_hash))
            except urllib.error.HTTPError as e:
                if file.required:
                    raise
                continue

            if file.should_verify_checksum:
                if not verify_checksum(dest_path):
                    print(f"Checksum mismatch for blob {dest_path}, retrying download...")
                    os.remove(dest_path)
                    file.download(dest_path, self.get_snapshot_directory(snapshot_hash))
                    if not verify_checksum(dest_path):
                        raise ValueError(f"Checksum verification failed for blob {dest_path}")

            os.symlink(blob_relative_path, self.get_snapshot_file_path(snapshot_hash, file.name))
