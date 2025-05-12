# The following code is inspired from: https://github.com/ericcurtin/lm-pull/blob/main/lm-pull.py

import fcntl
import os
from configparser import ConfigParser


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


class IniFile:

    def __init__(self, filename: str):
        self.filename = filename
        self.config = ConfigParser()
        self.config.optionxform = lambda option: option

    def add(self, section: str, key: str, value: str):
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value

    def write(self, dirpath: str):
        dirpath = os.path.expanduser(dirpath)
        with open(os.path.join(dirpath, self.filename), "w") as f:
            self.config.write(f, space_around_delimiters=False)
            f.flush()
