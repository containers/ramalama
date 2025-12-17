import os
import shutil
import urllib.error
from collections import Counter
from http import HTTPStatus
from pathlib import Path
from typing import Optional, Sequence, Tuple

from ramalama.common import perror, sanitize_filename, verify_checksum
from ramalama.endian import EndianMismatchError, get_system_endianness
from ramalama.logger import logger
from ramalama.model_inspect.gguf_parser import GGUFInfoParser, GGUFModelInfo
from ramalama.model_store import go2jinja
from ramalama.model_store.constants import DIRECTORY_NAME_BLOBS, DIRECTORY_NAME_REFS, DIRECTORY_NAME_SNAPSHOTS
from ramalama.model_store.global_store import GlobalModelStore
from ramalama.model_store.reffile import RefJSONFile, StoreFile, StoreFileType, migrate_reffile_to_refjsonfile
from ramalama.model_store.snapshot_file import (
    LocalSnapshotFile,
    SnapshotFile,
    SnapshotFileType,
    validate_snapshot_files,
)
from ramalama.model_store.template_conversion import (
    TemplateConversionError,
    convert_go_to_jinja,
    ensure_jinja_openai_compatibility,
    is_openai_jinja,
)
from ramalama.path_utils import create_file_link


def map_to_store_file_type(snapshot_type: SnapshotFileType) -> StoreFileType:
    mapping = {
        SnapshotFileType.GGUFModel: StoreFileType.GGUF_MODEL,
        SnapshotFileType.ChatTemplate: StoreFileType.CHAT_TEMPLATE,
        SnapshotFileType.Mmproj: StoreFileType.MMPROJ,
        SnapshotFileType.SafetensorModel: StoreFileType.SAFETENSOR_MODEL,
    }
    return mapping.get(snapshot_type, StoreFileType.OTHER)


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
        ref_file_path = self.get_ref_file_path(model_tag)
        ref_file = migrate_reffile_to_refjsonfile(ref_file_path, self.snapshots_directory)
        if ref_file is None:
            if os.path.exists(ref_file_path):
                ref_file = RefJSONFile.from_path(ref_file_path)
        if ref_file is not None:
            if ref_file.version != RefJSONFile.version:
                # 0.13.0 chat template conversion logic was wrong, force a refresh
                ref_file.version = RefJSONFile.version
                self._ensure_chat_template(ref_file, snapshot_hash=ref_file.hash)
        return ref_file

    def update_ref_file(
        self, model_tag: str, snapshot_hash: str = "", snapshot_files: Optional[list[SnapshotFile]] = None
    ) -> Optional[RefJSONFile]:
        if snapshot_files is None:
            snapshot_files = []

        ref_file: RefJSONFile | None = self.get_ref_file(model_tag)
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

    def get_safetensor_blob_path(self, model_tag: str, requested_filename: str) -> Optional[str]:
        ref_file = self.get_ref_file(model_tag)
        if ref_file is None:
            return None
        safetensor_files = ref_file.safetensor_model_files
        if not safetensor_files:
            return None
        matched = next((f for f in safetensor_files if f.name == requested_filename), None)
        chosen = matched if matched is not None else safetensor_files[0]
        return self.get_blob_file_path(chosen.hash)

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
        cached_files: list[str] = []

        ref_file: RefJSONFile | None = self.get_ref_file(model_tag)
        if ref_file is None:
            return ("", cached_files, False)

        # TODO: Remove in following releases
        # Temporary migration of .safetensors model files which were previously stored as OTHER
        should_write = False
        for file in ref_file.files:
            if file.name.endswith(".safetensors") and file.type != StoreFileType.SAFETENSOR_MODEL:
                file.type = StoreFileType.SAFETENSOR_MODEL
                should_write = True
        if should_write:
            ref_file.write_to_file()

        for file in ref_file.files:
            path = self.get_blob_file_path(file.hash)
            if os.path.exists(path):
                cached_files.append(file.name)

        return (ref_file.hash, cached_files, len(cached_files) == len(ref_file.files))

    def _prepare_new_snapshot(
        self, model_tag: str, snapshot_hash: str, snapshot_files: list[SnapshotFile]
    ) -> RefJSONFile:
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
        return ref_file

    def _download_snapshot_files(
        self, ref_file: RefJSONFile, snapshot_hash: str, snapshot_files: Sequence[SnapshotFile]
    ):
        for file in snapshot_files:
            dest_path = self.get_blob_file_path(file.hash)
            try:
                file.download(dest_path, self.get_snapshot_directory(snapshot_hash))
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

            blob_absolute_path = self.get_blob_file_path(file.hash)
            # Use cross-platform file linking (hardlink/symlink/copy)
            create_file_link(blob_absolute_path, link_path)

        # save updated ref file
        ref_file.write_to_file()

    def _try_convert_existing_chat_template(self, ref_file: RefJSONFile, snapshot_hash: str) -> bool:
        for file in ref_file.chat_templates:
            chat_template_file_path = self.get_blob_file_path(file.hash)
            with open(chat_template_file_path, "r") as template_file:
                chat_template = template_file.read()

            if not go2jinja.is_go_template(chat_template):
                if is_openai_jinja(chat_template):
                    return True
                else:
                    normalized_template = ensure_jinja_openai_compatibility(chat_template)
            else:
                try:
                    normalized_template = convert_go_to_jinja(chat_template)
                except TemplateConversionError as e:
                    logger.debug(f"Failed to convert template: {e}")
                    continue

            files = [
                LocalSnapshotFile(
                    normalized_template.encode("utf-8"), "chat_template_converted", SnapshotFileType.ChatTemplate
                )
            ]
            self._update_snapshot(ref_file, snapshot_hash, files)
            return True

        return False

    def _ensure_chat_template(self, ref_file: RefJSONFile, snapshot_hash: str):
        # Give preference to the embedded chat template as it's most likely to be
        # compatible with llama.cpp

        def get_embedded_template() -> str | None:
            models = ref_file.model_files
            if not models:
                return None

            # Only the first model file is considered for chat template extraction
            model_file_path = self.get_blob_file_path(models[0].hash)
            if not GGUFInfoParser.is_model_gguf(model_file_path):
                return None

            # Parse model, first and second parameter are irrelevant here
            info: GGUFModelInfo = GGUFInfoParser.parse("model", "registry", model_file_path)
            return info.get_chat_template()

        tmpl = get_embedded_template()

        if tmpl is None:
            self._try_convert_existing_chat_template(ref_file, snapshot_hash)
            return

        needs_conversion = go2jinja.is_go_template(tmpl)

        # Only jinja templates are usable for the supported backends, therefore don't mark file as
        # chat template if it is a Go Template (ollama-specific)
        files = [
            LocalSnapshotFile(
                tmpl.encode("utf-8"),
                "chat_template_extracted",
                SnapshotFileType.Other if needs_conversion else SnapshotFileType.ChatTemplate,
            )
        ]
        if needs_conversion:
            try:
                desired_template = convert_go_to_jinja(tmpl)
                files.append(
                    LocalSnapshotFile(
                        desired_template.encode("utf-8"), "chat_template_converted", SnapshotFileType.ChatTemplate
                    )
                )
            except Exception as ex:
                logger.debug(f"Failed to convert Go Template to Jinja: {ex}")
        else:
            for file in ref_file.files:
                if file.name == "chat_template_converted":
                    # Should not exist but 0.13.0 needs_conversion logic was inverted
                    self._remove_blob_path(Path(self.get_snapshot_file_path(ref_file.hash, file.name)))
                    ref_file.remove_file(file.hash)
                    break
        self._update_snapshot(ref_file, snapshot_hash, files)

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

    def new_snapshot(self, model_tag: str, snapshot_hash: str, snapshot_files: list[SnapshotFile], verify: bool = True):
        snapshot_hash = sanitize_filename(snapshot_hash)

        try:
            ref_file = self._prepare_new_snapshot(model_tag, snapshot_hash, snapshot_files)
            self._download_snapshot_files(ref_file, snapshot_hash, snapshot_files)
            self._ensure_chat_template(ref_file, snapshot_hash)
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
            if verify:
                self.verify_snapshot(model_tag)
        except EndianMismatchError as ex:
            perror(f"Verification of snapshot failed: {ex}")
            perror("Removing snapshot...")
            self.remove_snapshot(model_tag)
            raise ex

    def _update_snapshot(
        self, ref_file: RefJSONFile, snapshot_hash: str, new_snapshot_files: Sequence[SnapshotFile]
    ) -> bool:
        validate_snapshot_files(new_snapshot_files)
        snapshot_hash = sanitize_filename(snapshot_hash)

        if not self.directory_setup_exists():
            return False

        # update ref file with deduplication by file hash
        existing_file_hashes = {f.hash for f in ref_file.files}
        for new_snapshot_file in new_snapshot_files:
            if new_snapshot_file.hash not in existing_file_hashes:
                ref_file.files.append(
                    StoreFile(
                        new_snapshot_file.hash,
                        new_snapshot_file.name,
                        map_to_store_file_type(new_snapshot_file.type),
                    )
                )
        ref_file.write_to_file()

        self._download_snapshot_files(ref_file, snapshot_hash, new_snapshot_files)
        return True

    def _remove_blob_path(self, blob_path: Path):
        try:
            if blob_path.exists() and Path(self.base_path) in blob_path.parents:
                blob_path.unlink(missing_ok=True)
                logger.debug(f"Removed blob file '{blob_path}'")
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
        refs = [ref for tag in model_tags if (ref := self.get_ref_file(tag))]

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
                blob_absolute_path = Path(self.get_blob_file_path(file.hash))
                self._remove_blob_path(blob_absolute_path)
            else:
                logger.debug(f"Not removing blob {file} refcount={blob_refcount}")

        # Remove snapshot directory
        if snapshot_refcount <= 1:
            # FIXME: this only cleans up .partial files where the blob hash equals the snapshot hash
            partial_blob_file_path = Path(self.get_partial_blob_file_path(ref_file.hash))
            self._remove_blob_path(partial_blob_file_path)
            snapshot_directory = self.get_snapshot_directory_from_tag(model_tag)
            shutil.rmtree(snapshot_directory, ignore_errors=True)
            logger.debug(f"Snapshot removed {ref_file.hash}")
        else:
            logger.debug(f"Not removing snapshot {ref_file.hash} refcount={snapshot_refcount}")

        # Remove ref file, ignore if file is not found
        Path(self.get_ref_file_path(model_tag)).unlink(missing_ok=True)
        return True
