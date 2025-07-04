import os
import shutil
import urllib.error
from collections import Counter
from http import HTTPStatus
from pathlib import Path
from typing import Optional, Tuple

import ramalama.model_store.go2jinja as go2jinja
from ramalama.common import generate_sha256, perror, verify_checksum
from ramalama.endian import EndianMismatchError, get_system_endianness
from ramalama.logger import logger
from ramalama.model_inspect.gguf_parser import GGUFInfoParser, GGUFModelInfo
from ramalama.model_store.constants import DIRECTORY_NAME_BLOBS, DIRECTORY_NAME_REFS, DIRECTORY_NAME_SNAPSHOTS
from ramalama.model_store.global_store import GlobalModelStore
from ramalama.model_store.reffile import RefFile, RefJSONFile, StoreFile, StoreFileType
from ramalama.model_store.snapshot_file import (
    LocalSnapshotFile,
    SnapshotFile,
    SnapshotFileType,
    validate_snapshot_files,
)


def sanitize_filename(filename: str) -> str:
    return filename.replace(":", "-")


def map_to_store_file_type(snapshot_type: SnapshotFileType) -> StoreFileType:
    ftype = StoreFileType.OTHER
    if snapshot_type == SnapshotFileType.Model:
        ftype = StoreFileType.GGUF_MODEL
    if snapshot_type == SnapshotFileType.ChatTemplate:
        ftype = StoreFileType.CHAT_TEMPLATE
    if snapshot_type == SnapshotFileType.Mmproj:
        ftype = StoreFileType.MMPROJ

    return ftype


def map_ref_file(ref_file: RefFile, snapshot_directory: str) -> RefJSONFile:
    ref = RefJSONFile(
        hash=ref_file.hash,
        path=f"{ref_file.path}.json",
        files=[],
    )

    def determine_type(filename: str) -> StoreFileType:
        if filename == ref_file.model_name:
            return StoreFileType.GGUF_MODEL
        if filename == ref_file.chat_template_name:
            return StoreFileType.CHAT_TEMPLATE
        if filename == ref_file.mmproj_name:
            return StoreFileType.MMPROJ
        return StoreFileType.OTHER

    def determine_blob_hash(filename: str) -> str:
        blob_path = Path(os.path.join(snapshot_directory, sanitize_filename(ref_file.hash), filename)).resolve()
        if not os.path.exists(blob_path):
            return generate_sha256(filename)
        return blob_path.stem

    for file in ref_file.filenames:
        ftype = determine_type(file)
        ref.files.append(StoreFile(determine_blob_hash(file), file, ftype))

    return ref


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
        return os.path.join(self.base_path, self.model_type, self.model_organization, self.model_name)

    @property
    def blobs_directory(self) -> str:
        return os.path.join(self.model_base_directory, DIRECTORY_NAME_BLOBS)

    @property
    def refs_directory(self) -> str:
        return os.path.join(self.model_base_directory, DIRECTORY_NAME_REFS)

    @property
    def snapshots_directory(self) -> str:
        return os.path.join(self.model_base_directory, DIRECTORY_NAME_SNAPSHOTS)

    def file_exists(self, file_path: str) -> bool:
        return os.path.exists(file_path)

    def get_ref_file_path(self, model_tag: str) -> str:
        return os.path.join(self.refs_directory, f"{model_tag}.json")

    def get_ref_file(self, model_tag: str) -> Optional[RefJSONFile]:
        # Check if a ref file in old format is present by removing the file extension
        old_ref_file_path = self.get_ref_file_path(model_tag).replace(".json", "")
        if os.path.exists(old_ref_file_path):
            ref = map_ref_file(RefFile.from_path(old_ref_file_path), self.snapshots_directory)
            ref.write_to_file()
            try:
                os.remove(old_ref_file_path)
            except Exception as ex:
                logger.debug(f"Failed to remove old ref file '{old_ref_file_path}'\n: {ex}")

            return ref

        ref_file_path = self.get_ref_file_path(model_tag)
        if not os.path.exists(ref_file_path):
            return None

        return RefJSONFile.from_path(ref_file_path)

    def update_ref_file(
        self, model_tag: str, snapshot_hash: str = "", snapshot_files: list[SnapshotFile] = []
    ) -> Optional[RefJSONFile]:
        ref_file: RefJSONFile = self.get_ref_file(model_tag)
        if ref_file is None:
            return None

        if snapshot_hash != "":
            ref_file.hash = snapshot_hash
        if snapshot_files != []:
            ref_file.files = []
        for file in snapshot_files:
            ref_file.files.append(StoreFile(file.hash, file.name, map_to_store_file_type(file.type)))

        ref_file.write_to_file()

        return ref_file

    def get_snapshot_hash(self, model_tag: str) -> str:
        ref_file = self.get_ref_file(model_tag)
        if ref_file is None:
            return ""
        return sanitize_filename(ref_file.hash)

    def get_snapshot_directory_from_tag(self, model_tag: str) -> str:
        return os.path.join(self.snapshots_directory, self.get_snapshot_hash(model_tag))

    def get_snapshot_directory(self, hash: str) -> str:
        return os.path.join(self.snapshots_directory, hash)

    def get_snapshot_file_path(self, tag_hash: str, filename: str) -> str:
        return os.path.join(self.snapshots_directory, sanitize_filename(tag_hash), filename)

    def get_blob_file_path(self, file_hash: str) -> str:
        return os.path.join(self.blobs_directory, sanitize_filename(file_hash))

    def get_blob_file_path_by_name(self, tag_hash: str, filename: str) -> str:
        return str(Path(self.get_snapshot_file_path(tag_hash, filename)).resolve())

    def get_blob_file_hash(self, tag_hash: str, filename: str) -> str:
        return os.path.basename(self.get_blob_file_path_by_name(tag_hash, filename))

    def get_partial_blob_file_path(self, file_hash: str) -> str:
        return self.get_blob_file_path(file_hash) + ".partial"

    def ensure_directory_setup(self) -> None:
        os.makedirs(self.blobs_directory, exist_ok=True)
        os.makedirs(self.refs_directory, exist_ok=True)
        os.makedirs(self.snapshots_directory, exist_ok=True)

    def directory_setup_exists(self) -> bool:
        return (
            os.path.exists(self.blobs_directory)
            and os.path.exists(self.refs_directory)
            and os.path.exists(self.snapshots_directory)
        )

    def get_cached_files(self, model_tag: str) -> Tuple[str, list[str], bool]:
        cached_files = []

        ref_file: RefJSONFile = self.get_ref_file(model_tag)
        if ref_file is None:
            return ("", cached_files, False)

        for file in ref_file.files:
            path = self.get_blob_file_path(file.hash)
            if os.path.exists(path):
                cached_files.append(file.name)

        return (ref_file.hash, cached_files, len(cached_files) == len(ref_file.files))

    def _prepare_new_snapshot(self, model_tag: str, snapshot_hash: str, snapshot_files: list[SnapshotFile]):
        validate_snapshot_files(snapshot_files)
        self.ensure_directory_setup()

        ref_file = self.get_ref_file(model_tag)
        if ref_file is None:
            ref_file = RefJSONFile(snapshot_hash, self.get_ref_file_path(model_tag), [])
            for file in snapshot_files:
                ref_file.files.append(StoreFile(file.hash, file.name, map_to_store_file_type(file.type)))

            ref_file.write_to_file()

        snapshot_directory = self.get_snapshot_directory(snapshot_hash)
        os.makedirs(snapshot_directory, exist_ok=True)

    def _download_snapshot_files(self, model_tag: str, snapshot_hash: str, snapshot_files: list[SnapshotFile]):
        ref_file = self.get_ref_file(model_tag)

        for file in snapshot_files:
            dest_path = self.get_blob_file_path(file.hash)
            blob_relative_path = ""
            try:
                blob_relative_path = file.download(dest_path, self.get_snapshot_directory(snapshot_hash))
            except urllib.error.HTTPError as ex:
                if file.required:
                    raise ex
                # remove file from ref file list to prevent a retry to download it
                if ex.code == HTTPStatus.NOT_FOUND:
                    ref_file.remove_file(file.hash)
                continue

            if file.should_verify_checksum:
                if not verify_checksum(dest_path):
                    logger.info(f"Checksum mismatch for blob {dest_path}, retrying download ...")
                    os.remove(dest_path)
                    file.download(dest_path, self.get_snapshot_directory(snapshot_hash))
                    if not verify_checksum(dest_path):
                        raise ValueError(f"Checksum verification failed for blob {dest_path}")

            link_path = self.get_snapshot_file_path(snapshot_hash, file.name)
            try:
                os.symlink(blob_relative_path, link_path)
            except FileExistsError:
                os.unlink(link_path)
                os.symlink(blob_relative_path, link_path)

        # save updated ref file
        ref_file.write_to_file()

    def _ensure_chat_template(self, model_tag: str, snapshot_hash: str, snapshot_files: list[SnapshotFile]):
        model_file: SnapshotFile | None = None
        for file in snapshot_files:
            # Give preference to a chat template that has been specified in the file list
            if file.type == SnapshotFileType.ChatTemplate:
                chat_template_file_path = self.get_blob_file_path(file.hash)
                chat_template = ""
                with open(chat_template_file_path, "r") as file:
                    chat_template = file.read()

                if not go2jinja.is_go_template(chat_template):
                    return

                try:
                    jinja_template = go2jinja.go_to_jinja(chat_template)
                    files = [
                        LocalSnapshotFile(jinja_template, "chat_template_converted", SnapshotFileType.ChatTemplate)
                    ]
                    self.update_snapshot(model_tag, snapshot_hash, files)
                except Exception as ex:
                    logger.debug(f"Failed to convert Go Template to Jinja: {ex}")
                return
            if file.type == SnapshotFileType.Model:
                model_file = file

        # Could not find model file in store
        if model_file is None:
            return

        model_file_path = self.get_blob_file_path(model_file.hash)
        if not GGUFInfoParser.is_model_gguf(model_file_path):
            return

        # Parse model, first and second parameter are irrelevant here
        info: GGUFModelInfo = GGUFInfoParser.parse("model", "registry", model_file_path)
        tmpl = info.get_chat_template()
        if tmpl == "":
            return

        is_go_template = go2jinja.is_go_template(tmpl)

        # Only jinja templates are usable for the supported backends, therefore don't mark file as
        # chat template if it is a Go Template (ollama-specific)
        files = [
            LocalSnapshotFile(
                tmpl, "chat_template", SnapshotFileType.Other if is_go_template else SnapshotFileType.ChatTemplate
            )
        ]
        if is_go_template:
            try:
                jinja_template = go2jinja.go_to_jinja(tmpl)
                files.append(
                    LocalSnapshotFile(jinja_template, "chat_template_converted", SnapshotFileType.ChatTemplate)
                )
            except Exception as ex:
                logger.debug(f"Failed to convert Go Template to Jinja: {ex}")

        self.update_snapshot(model_tag, snapshot_hash, files)

    def _verify_endianness(self, model_tag: str):
        ref_file = self.get_ref_file(model_tag)
        if ref_file is None:
            return

        for model_file in ref_file.model_files:
            model_path = self.get_blob_file_path(model_file.hash)

            # only check endianness for gguf models
            if not GGUFInfoParser.is_model_gguf(model_path):
                return

            model_endianness = GGUFInfoParser.get_model_endianness(model_path)
            host_endianness = get_system_endianness()
            if host_endianness != model_endianness:
                raise EndianMismatchError(host_endianness, model_endianness)

    def verify_snapshot(self, model_tag: str):
        self._verify_endianness(model_tag)
        self._store.verify_snapshot()

    def new_snapshot(self, model_tag: str, snapshot_hash: str, snapshot_files: list[SnapshotFile]):
        snapshot_hash = sanitize_filename(snapshot_hash)

        try:
            self._prepare_new_snapshot(model_tag, snapshot_hash, snapshot_files)
            self._download_snapshot_files(model_tag, snapshot_hash, snapshot_files)
            self._ensure_chat_template(model_tag, snapshot_hash, snapshot_files)
        except urllib.error.HTTPError as ex:
            perror(f"Failed to fetch required file: {ex}")
            perror("Removing snapshot...")
            self.remove_snapshot(model_tag)
            raise ex
        except Exception as ex:
            perror("Removing snapshot...")
            self.remove_snapshot(model_tag)
            raise ex

        try:
            self.verify_snapshot(model_tag)
        except EndianMismatchError as ex:
            perror(f"Verification of snapshot failed: {ex}")
            perror("Removing snapshot...")
            self.remove_snapshot(model_tag)
            raise ex

    def update_snapshot(self, model_tag: str, snapshot_hash: str, new_snapshot_files: list[SnapshotFile]) -> bool:
        validate_snapshot_files(new_snapshot_files)
        snapshot_hash = sanitize_filename(snapshot_hash)

        if not self.directory_setup_exists():
            return False

        ref_file = self.get_ref_file(model_tag)
        if ref_file is None:
            return False

        # update ref file with deduplication by file hash
        existing_file_hashes = {f.hash for f in ref_file.files}
        for new_snapshot_file in new_snapshot_files:
            if new_snapshot_file.hash not in existing_file_hashes:
                ref_file.files.append(
                    StoreFile(
                        new_snapshot_file.hash, new_snapshot_file.name, map_to_store_file_type(new_snapshot_file.type)
                    )
                )
        ref_file.write_to_file()

        self._download_snapshot_files(model_tag, snapshot_hash, new_snapshot_files)
        return True

    def _remove_blob_file(self, snapshot_file_path: str):
        blob_path = Path(snapshot_file_path).resolve()
        try:
            if os.path.exists(blob_path) and Path(self.base_path) in blob_path.parents:
                os.remove(blob_path)
                logger.debug(f"Removed blob for '{snapshot_file_path}'")
        except Exception as ex:
            logger.error(f"Failed to remove blob file '{blob_path}': {ex}")

    def _get_refcounts(self, snapshot_hash: str) -> tuple[int, Counter[str]]:
        # get all ref file names and remove the last suffix, i.e. .json, if it exists
        # so that only the model tag remains
        model_tags = [
            Path(entry).stem
            for entry in os.listdir(self.refs_directory)
            if os.path.isfile(os.path.join(self.refs_directory, entry))
        ]
        refs = [self.get_ref_file(tag) for tag in model_tags]

        blob_refcounts = Counter(file.name for ref in refs for file in ref.files)

        snap_refcount = sum(ref.hash == snapshot_hash for ref in refs)

        return snap_refcount, blob_refcounts

    def remove_snapshot(self, model_tag: str) -> bool:
        ref_file = self.get_ref_file(model_tag)

        if ref_file is None:
            return False

        snapshot_refcount, blob_refcounts = self._get_refcounts(ref_file.hash)

        # Remove all blobs first
        for file in ref_file.files:
            blob_refcount = blob_refcounts.get(file.name, 0)
            if blob_refcount <= 1:
                self._remove_blob_file(self.get_snapshot_file_path(ref_file.hash, file.name))
            else:
                logger.debug(f"Not removing blob {file} refcount={blob_refcount}")

        # Remove snapshot directory
        if snapshot_refcount <= 1:
            # FIXME: this only cleans up .partial files where the blob hash equals the snapshot hash
            self._remove_blob_file(self.get_partial_blob_file_path(ref_file.hash))
            snapshot_directory = self.get_snapshot_directory_from_tag(model_tag)
            shutil.rmtree(snapshot_directory, ignore_errors=True)
            logger.debug(f"Snapshot removed {ref_file.hash}")
        else:
            logger.debug(f"Not removing snapshot {ref_file.hash} refcount={snapshot_refcount}")

        # Remove ref file, ignore if file is not found
        ref_file_path = self.get_ref_file_path(model_tag)
        try:
            os.remove(ref_file_path)
        except FileNotFoundError:
            pass

        return True
