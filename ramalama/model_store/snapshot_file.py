import os
from enum import IntEnum
from typing import Dict

from ramalama.common import generate_sha256
from ramalama.http_client import download_file
from ramalama.logger import logger


class SnapshotFileType(IntEnum):
    Model = 1
    ChatTemplate = 2
    Other = 3
    Mmproj = 4


class SnapshotFile:
    def __init__(
        self,
        url: str,
        header: Dict,
        hash: str,
        name: str,
        type: SnapshotFileType,
        should_show_progress: bool = False,
        should_verify_checksum: bool = False,
        required: bool = True,
    ):
        self.url: str = url
        self.header: Dict = header
        self.hash: str = hash
        self.name: str = name
        self.type: SnapshotFileType = type
        self.should_show_progress: bool = should_show_progress
        self.should_verify_checksum: bool = should_verify_checksum
        self.required: bool = required

    def download(self, blob_file_path: str, snapshot_dir: str) -> str:
        if not os.path.exists(blob_file_path):
            download_file(
                url=self.url,
                headers=self.header,
                dest_path=blob_file_path,
                show_progress=self.should_show_progress,
            )
        else:
            logger.debug(f"Using cached blob for {self.name} ({os.path.basename(blob_file_path)})")
        return os.path.relpath(blob_file_path, start=snapshot_dir)


class LocalSnapshotFile(SnapshotFile):
    def __init__(
        self,
        content: str,
        name: str,
        type: SnapshotFileType,
        should_show_progress: bool = False,
        should_verify_checksum: bool = False,
        required: bool = True,
    ):
        super().__init__(
            "",
            "",
            generate_sha256(content),
            name,
            type,
            should_show_progress,
            should_verify_checksum,
            required,
        )
        self.content = content

    def download(self, blob_file_path, snapshot_dir):
        with open(blob_file_path, "w") as file:
            file.write(self.content)
            file.flush()
        return os.path.relpath(blob_file_path, start=snapshot_dir)


def validate_snapshot_files(snapshot_files: list[SnapshotFile]):
    chat_template_files = []
    mmproj_files = []
    for file in snapshot_files:
        if file.type == SnapshotFileType.ChatTemplate:
            chat_template_files.append(file)
        if file.type == SnapshotFileType.Mmproj:
            mmproj_files.append(file)

    if len(chat_template_files) > 1:
        raise ValueError(f"Only one chat template supported, got {len(chat_template_files)}: {chat_template_files}")
    if len(mmproj_files) > 1:
        raise ValueError(f"Only one mmproj supported, got {len(mmproj_files)}: {mmproj_files}")
