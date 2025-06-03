# The following code is inspired from: https://github.com/ericcurtin/lm-pull/blob/main/lm-pull.py

import fcntl
import os


class File:
    def __init__(self):
        self.file = None
        self.fd = -1

    def open(self, filename, mode):
        self.file = open(filename, mode)
        return self.file

    def lock(self):
        if self.file:
            self.fd = self.file.fileno()
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self.fd = -1
                return 1

        return 0

    def __del__(self):
        if self.fd >= 0:
            fcntl.flock(self.fd, fcntl.LOCK_UN)

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
        self.sections = {}

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
