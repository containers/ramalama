from __future__ import annotations

import logging
import os
import stat

from ramalama.log_levels import LogLevel

DEFAULT_LOG_DIR = "/var/log/ramalama"

# Global logger
logger = logging.getLogger("ramalama-daemon")


def configure_logger(lvl: LogLevel = LogLevel.WARNING, log_file: str = DEFAULT_LOG_DIR) -> None:
    if logger.hasHandlers():
        return

    logger.setLevel(lvl)

    fmt = "%(asctime)s - %(levelname)s - %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt)

    os.makedirs(log_file, mode=0o750, exist_ok=True)
    directory_stat = os.stat(log_file, follow_symlinks=False)
    if not stat.S_ISDIR(directory_stat.st_mode):
        raise NotADirectoryError(log_file)
    if directory_stat.st_mode & 0o002:
        raise PermissionError(log_file)

    log_file_path = os.path.join(log_file, "ramalama-daemon.log")
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(log_file_path, flags, 0o640)
    file_stat = os.fstat(fd)
    if not stat.S_ISREG(file_stat.st_mode):
        os.close(fd)
        raise PermissionError(log_file_path)

    handler = logging.StreamHandler(os.fdopen(fd, "a"))
    handler.setLevel(lvl)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
