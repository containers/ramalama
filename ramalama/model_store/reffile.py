import json
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Optional

from ramalama.common import generate_sha256, sanitize_filename
from ramalama.logger import logger


class RefFile:
    SEP = "---"
    MODEL_SUFFIX = "model"
    CHAT_TEMPLATE_SUFFIX = "chat"
    MMPROJ_SUFFIX = "mmproj"

    def __init__(self) -> None:
        self.hash: str = ""
        self.filenames: list[str] = []
        self.model_name: str = ""
        self.chat_template_name: str = ""
        self.mmproj_name: str = ""
        self._path: str = ""

    @property
    def path(self) -> str:
        return self._path

    @staticmethod
    def from_path(path: str) -> "RefFile":
        ref_file = RefFile()
        ref_file._path = path
        with open(path, "r") as file:
            ref_file.hash = file.readline().strip()
            filename = file.readline().strip()
            while filename != "":
                parts = filename.split(RefFile.SEP)
                if len(parts) != 2:
                    ref_file.filenames.append(filename)
                    filename = file.readline().strip()
                    continue

                ref_file.filenames.append(parts[0])
                if parts[1] == RefFile.MODEL_SUFFIX:
                    ref_file.model_name = parts[0]
                if parts[1] == RefFile.CHAT_TEMPLATE_SUFFIX:
                    ref_file.chat_template_name = parts[0]
                if parts[1] == RefFile.MMPROJ_SUFFIX:
                    ref_file.mmproj_name = parts[0]

                filename = file.readline().strip()
        return ref_file

    def remove_file(self, name: str):
        if name in self.filenames:
            self.filenames.remove(name)

            if self.chat_template_name == name:
                self.chat_template_name = ""
            if self.model_name == name:
                self.model_name = ""
            if self.mmproj_name == name:
                self.mmproj_name = ""

    def serialize(self) -> str:
        lines = [self.hash]
        for filename in self.filenames:
            line = f"{filename}{RefFile.SEP}"
            if filename == self.model_name:
                line = line + RefFile.MODEL_SUFFIX
            if filename == self.chat_template_name:
                line = line + RefFile.CHAT_TEMPLATE_SUFFIX
            if filename == self.mmproj_name:
                line = line + RefFile.MMPROJ_SUFFIX
            lines.append(line)
        return "\n".join(lines)

    def write_to_file(self):
        with open(self.path, "w") as file:
            file.write(self.serialize())
            file.flush()

    @staticmethod
    def map_to_refjsonfile(ref_file_path: str, snapshot_directory: str) -> "RefJSONFile":
        ref_file = RefFile.from_path(ref_file_path)

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


#
# Temporary migration routine to ensure smooth transition to new RefFile format
#
def migrate_reffile_to_refjsonfile(ref_file_path: str, snapshot_directory: str) -> Optional["RefJSONFile"]:
    # Check if a ref file in old format is present by removing the file extension
    old_ref_file_path = ref_file_path.replace(".json", "")
    if os.path.exists(old_ref_file_path):
        logger.debug(f"Migrating old ref file '{old_ref_file_path}' to new format")
        ref: RefJSONFile = RefFile.map_to_refjsonfile(old_ref_file_path, snapshot_directory)
        ref.write_to_file()
        try:
            os.remove(old_ref_file_path)
            return ref
        except Exception as ex:
            logger.debug(f"Failed to remove old ref file '{old_ref_file_path}'\n: {ex}")

    return None


class StoreFileType(StrEnum):
    GGUF_MODEL = "gguf"
    MMPROJ = "mmproj"
    CHAT_TEMPLATE = "chat_template"
    OTHER = "other"

    @staticmethod
    def from_str(s: str) -> "StoreFileType":
        if s == StoreFileType.GGUF_MODEL.value:
            return StoreFileType.GGUF_MODEL
        if s == StoreFileType.MMPROJ.value:
            return StoreFileType.MMPROJ
        if s == StoreFileType.CHAT_TEMPLATE.value:
            return StoreFileType.CHAT_TEMPLATE
        return StoreFileType.OTHER


@dataclass
class StoreFile:
    hash: str
    name: str
    type: StoreFileType


@dataclass
class RefJSONFile:
    hash: str
    path: str
    files: list[StoreFile]

    version: str = "v1.0"

    def to_json(self) -> str:
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=2)

    def write_to_file(self):
        with open(self.path, "w") as file:
            file.write(self.to_json())
            file.flush()

    @property
    def model_files(self) -> list[StoreFile]:
        return [file for file in self.files if file.type == StoreFileType.GGUF_MODEL]

    @property
    def chat_templates(self) -> list[StoreFile]:
        return [file for file in self.files if file.type == StoreFileType.CHAT_TEMPLATE]

    @property
    def mmproj_files(self) -> list[StoreFile]:
        return [file for file in self.files if file.type == StoreFileType.MMPROJ]

    def remove_file(self, hash: str):
        for file in self.files:
            if file.hash == hash:
                self.files.remove(file)
                break

    @staticmethod
    def from_path(path: str) -> "RefJSONFile":
        with open(path, "r") as f:
            data = json.loads(f.read())

            ref_version = data["version"]
            ref_hash = data["hash"]
            ref_path = data["path"]
            ref_files = []
            for file in data["files"]:
                file_hash = file["hash"]
                file_name = file["name"]
                file_type = StoreFileType.from_str(file["type"])
                ref_files.append(StoreFile(file_hash, file_name, file_type))

            return RefJSONFile(
                version=ref_version,
                hash=ref_hash,
                path=ref_path,
                files=ref_files,
            )
