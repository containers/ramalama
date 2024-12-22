# The following code is inspired from: https://github.com/ericcurtin/lm-pull/blob/main/lm-pull.py

import fcntl


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
