import logging
import os
import typing

logger = logging.getLogger("ramalama-daemon")


def configure_logger(verbosity: str = "WARNING", log_file: str = "/var/tmp") -> None:
    lvl = logging.WARNING
    if verbosity in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        lvl = typing.cast(int, getattr(logging, verbosity))

    logger.setLevel(lvl)

    fmt = "%(asctime)s - %(levelname)s - %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt)

    log_file_path = os.path.join(log_file, "ramalama-daemon.log")
    handler = logging.FileHandler(log_file_path)
    handler.setLevel(lvl)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
