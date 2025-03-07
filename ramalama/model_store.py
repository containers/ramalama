import logging
import os
import shutil
import urllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import ramalama.oci
from ramalama.common import download_file, verify_checksum

LOGGER = logging.getLogger(__name__)


def sanitize_hash(filename: str) -> str:
    return filename.replace(":", "-")


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

    def serialize(self) -> str:
        return "\n".join([self.hash] + self.filenames)


@dataclass
class ModelFile:
    name: str
    modified: float
    size: int


DIRECTORY_NAME_BLOBS = "blobs"
DIRECTORY_NAME_REFS = "refs"
DIRECTORY_NAME_SNAPSHOTS = "snapshots"


class dotdict(dict):
    """dot.notation access to dictionary attributes"""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


class GlobalModelStore:

    def __init__(
        self,
        base_path: Path,
    ):
        self._store_base_path = os.path.join(base_path, "store")

    @property
    def path(self) -> str:
        return self._store_base_path

    def list_models(self, engine: str, debug: bool) -> Dict[str, List[ModelFile]]:
        models: Dict[str, List[ModelFile]] = {}

        for root, subdirs, _ in os.walk(self.path):
            if DIRECTORY_NAME_REFS in subdirs:
                ref_dir = os.path.join(root, DIRECTORY_NAME_REFS)
                for ref_file_name in os.listdir(ref_dir):
                    ref_file: RefFile = RefFile.from_path(os.path.join(ref_dir, ref_file_name))
                    model_name = f"{root.replace(self.path, "").replace(os.sep, "", 1)}:{ref_file_name}"

                    models[model_name] = []
                    for snapshot_file in ref_file.filenames:
                        snapshot_file_path = os.path.join(root, DIRECTORY_NAME_SNAPSHOTS, ref_file.hash, snapshot_file)
                        last_modified = os.path.getmtime(snapshot_file_path)
                        file_size = os.path.getsize(snapshot_file_path)
                        models[model_name].append(ModelFile(snapshot_file, last_modified, file_size))

        oci_models = ramalama.oci.list_models(
            dotdict(
                {
                    "engine": engine,
                    "debug": debug,
                }
            )
        )
        for oci_model in oci_models:
            name, modified, size = (oci_model["name"], oci_model["modified"], oci_model["size"])
            # ramalama.oci.list_models provides modified as timestamp string, convert it to unix timestamp
            modified_unix = datetime.fromisoformat(modified).timestamp()
            models[name] = [ModelFile(name, modified_unix, size)]

        return models

    # TODO:
    # iterating over all symlinks in snapshot dir, check valid
    def verify_snapshot(self):
        pass

    # TODO:
    # iterating over models and check
    #    1. for broken symlinks in snapshot dirs -> delete and update refs
    #    2. for blobs not reached by ref->snapshot chain -> delete
    #    3. for empty folders -> delete
    def cleanup(self):
        pass


class ModelStore:

    def __init__(
        self,
        store: GlobalModelStore,
        model_name: str,
        model_type: str,
        model_organization: str,
    ):
        self._store = store
        self._model_name = model_name
        self._model_type = model_type
        self._model_organization = model_organization

    @property
    def base_path(self) -> str:
        return self._store.path

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_organization(self) -> str:
        return self._model_organization if self._model_organization != "" else self._model_name

    @property
    def model_type(self) -> str:
        return self._model_type

    @property
    def model_base_directory(self) -> str:
        return os.path.join(self.base_path, self.model_type, self.model_organization)

    @property
    def blobs_directory(self) -> str:
        return os.path.join(self.model_base_directory, DIRECTORY_NAME_BLOBS)

    @property
    def refs_directory(self) -> str:
        return os.path.join(self.model_base_directory, DIRECTORY_NAME_REFS)

    @property
    def snapshots_directory(self) -> str:
        return os.path.join(self.model_base_directory, DIRECTORY_NAME_SNAPSHOTS)

    def tag_exists(self, model_tag: str) -> bool:
        return os.path.exists(self.get_ref_file_path(model_tag))

    def file_exists(self, file_path: str) -> bool:
        return os.path.exists(file_path)

    def get_ref_file_path(self, model_tag: str) -> str:
        return os.path.join(self.refs_directory, model_tag)

    def get_ref_file(self, model_tag: str) -> Optional[RefFile]:
        if not self.tag_exists(self.get_ref_file_path(model_tag)):
            return None

        return RefFile.from_path(self.get_ref_file_path(model_tag))

    def update_ref_file(
        self, model_tag: str, snapshot_hash: str = "", snapshot_files: list[SnapshotFile] = []
    ) -> Optional[RefFile]:
        ref_file_path = self.get_ref_file_path(model_tag)
        if not os.path.exists(ref_file_path):
            return None

        ref_file: RefFile = RefFile.from_path(self.get_ref_file_path(model_tag))
        if snapshot_hash != "":
            ref_file.hash = snapshot_hash
        if snapshot_files != []:
            ref_file.filenames = [file.name for file in snapshot_files]

        with open(ref_file_path, "w") as file:
            file.write(ref_file.serialize())
            file.flush()

        return ref_file

    def get_snapshot_hash(self, model_tag: str) -> str:
        ref_file = self.get_ref_file(model_tag)
        if ref_file is None:
            return ""
        return sanitize_hash(ref_file.hash)

    def get_snapshot_directory_from_tag(self, model_tag: str) -> str:
        return os.path.join(self.snapshots_directory, self.get_snapshot_hash(model_tag))

    def get_snapshot_directory(self, hash: str) -> str:
        return os.path.join(self.snapshots_directory, hash)

    def get_snapshot_file_path(self, tag_hash: str, filename: str) -> str:
        return os.path.join(self.snapshots_directory, sanitize_hash(tag_hash), filename)

    def get_blob_file_path(self, file_hash: str) -> str:
        return os.path.join(self.blobs_directory, sanitize_hash(file_hash))

    def get_partial_blob_file_path(self, file_hash: str) -> str:
        return self.get_blob_file_path(file_hash) + ".partial"

    def ensure_directory_setup(self) -> None:
        os.makedirs(self.blobs_directory, exist_ok=True)
        os.makedirs(self.refs_directory, exist_ok=True)
        os.makedirs(self.snapshots_directory, exist_ok=True)

    def get_cached_files(self, model_tag: str) -> Tuple[str, list[str], bool]:
        cached_files = []

        ref_file_path = self.get_ref_file_path(model_tag)
        if not self.file_exists(ref_file_path):
            return ("", cached_files, False)

        ref_file: RefFile = RefFile.from_path(ref_file_path)
        for file in ref_file.filenames:
            path = self.get_snapshot_file_path(ref_file.hash, file)
            if os.path.exists(path):
                cached_files.append(file)

        return (ref_file.hash, cached_files, len(cached_files) == len(ref_file.filenames))

    def prepare_new_snapshot(self, model_tag: str, snapshot_hash: str, snapshot_files: list[SnapshotFile]):
        self.ensure_directory_setup()

        ref_file_path = self.get_ref_file_path(model_tag)
        if not self.file_exists(ref_file_path):
            ref_file = RefFile()
            ref_file.hash = snapshot_hash
            ref_file.filenames = [file.name for file in snapshot_files]
            with open(ref_file_path, "w") as file:
                file.write(ref_file.serialize())
                file.flush()

        snapshot_directory = self.get_snapshot_directory(snapshot_hash)
        os.makedirs(snapshot_directory, exist_ok=True)

    def new_snapshot(self, model_tag: str, snapshot_hash: str, snapshot_files: list[SnapshotFile]):
        snapshot_hash = sanitize_hash(snapshot_hash)
        self.prepare_new_snapshot(model_tag, snapshot_hash, snapshot_files)

        for file in snapshot_files:
            dest_path = self.get_blob_file_path(file.hash)
            blob_relative_path = ""
            try:
                blob_relative_path = file.download(dest_path, self.get_snapshot_directory(snapshot_hash))
            except urllib.error.HTTPError:
                if file.required:
                    raise
                continue

            if file.should_verify_checksum:
                if not verify_checksum(dest_path):
                    LOGGER.info(f"Checksum mismatch for blob {dest_path}, retrying download...")
                    os.remove(dest_path)
                    file.download(dest_path, self.get_snapshot_directory(snapshot_hash))
                    if not verify_checksum(dest_path):
                        raise ValueError(f"Checksum verification failed for blob {dest_path}")

            os.symlink(blob_relative_path, self.get_snapshot_file_path(snapshot_hash, file.name))

    def _remove_blob_file(self, snapshot_file_path: str):
        blob_path = Path(snapshot_file_path).resolve()
        try:
            if os.path.exists(blob_path) and self.base_path in blob_path.parents:
                os.remove(blob_path)
                LOGGER.debug(f"Removed blob for '{snapshot_file_path}'")
        except Exception as ex:
            LOGGER.error(f"Failed to remove blob file '{blob_path}': {ex}")

    def remove_snapshot(self, model_tag: str):
        ref_file = self.get_ref_file(model_tag)

        # Remove all blobs first
        if ref_file is not None:
            for file in ref_file.filenames:
                self._remove_blob_file(self.get_snapshot_file_path(ref_file.hash, file))
                self._remove_blob_file(self.get_partial_blob_file_path(ref_file.hash))

        # Remove snapshot directory
        snapshot_directory = self.get_snapshot_directory_from_tag(model_tag)
        try:
            shutil.rmtree(snapshot_directory, ignore_errors=False)
        except Exception as ex:
            LOGGER.error(f"Failed to remove snapshot directory '{snapshot_directory}': {ex}")
            # only continue to remove the ref file when blobs and snapshot directory have been removed
            return

        # Remove ref file
        ref_file_path = self.get_ref_file_path(model_tag)
        try:
            os.remove(ref_file_path)
        except Exception as ex:
            LOGGER.error(f"Failed to remove ref file '{ref_file_path}': {ex}")
