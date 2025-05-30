import logging
import sys
import typing

logger = logging.getLogger("ramalama")


def configure_logger(verbosity="WARNING") -> None:
    global logger

    lvl = logging.WARNING
    if verbosity in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        lvl = typing.cast(int, getattr(logging, verbosity))

    logger.setLevel(lvl)

    fmt = "%(asctime)s - %(levelname)s - %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(lvl)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
