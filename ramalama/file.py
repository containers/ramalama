# The following code is inspired from: https://github.com/ericcurtin/lm-pull/blob/main/lm-pull.py

import os
import platform
from types import ModuleType
from typing import BinaryIO, cast

# Import platform-specific locking mechanisms
fcntl: ModuleType | None = None
if not_windows := (platform.system() != "Windows"):
    import fcntl


class File:
    def __init__(self) -> None:
        self.file: BinaryIO | None = None
        self.fd: int = -1

    def open(self, filename: str, mode: str) -> BinaryIO:
        if "b" not in mode:
            raise ValueError("File.open requires binary mode")
        self.file = cast(BinaryIO, open(filename, mode))
        return self.file

    def lock(self) -> int:
        if self.file:
            self.fd = self.file.fileno()
            if fcntl is not None:
                try:
                    # Unix file locking using fcntl
                    fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except (BlockingIOError, OSError):
                    self.fd = -1
                    return 1
        return 0

    def __del__(self):
        if self.fd >= 0:
            if fcntl is not None:
                try:
                    # Unlock on Unix
                    fcntl.flock(self.fd, fcntl.LOCK_UN)
                except OSError:
                    pass  # File may already be closed

        if self.file:
            self.file.close()


class PlainFile:
    def __init__(self, filename: str, content: str = ""):
        self.filename = filename
        self.content = content

    def write(self, dirpath: str):
        dirpath = os.path.expanduser(dirpath)
        with open(os.path.join(dirpath, self.filename), "w") as f:
            f.write(self.content)
            f.flush()


class UnitFile:
    def __init__(self, filename: str):
        self.filename = filename
        self.sections: dict[str, dict[str, list[str]]] = {}

    def add(self, section: str, key: str, value: str = ""):
        if section not in self.sections:
            self.sections[section] = {}
        if key not in self.sections[section]:
            self.sections[section][key] = []
        self.sections[section][key].append(value)

    def write(self, dirpath: str):
        dirpath = os.path.expanduser(dirpath)
        with open(os.path.join(dirpath, self.filename), "w") as f:
            self._write(f)

    def _write(self, f):
        comments = self.sections.get('comment', {})
        for section in comments:
            f.write(f'{section}\n')

        for section, section_items in self.sections.items():
            if section == "comment":
                continue
            f.write(f'[{section}]\n')
            for key, values in section_items.items():
                for value in values:
                    f.write(f'{key}={value}\n')
            f.write('\n')
