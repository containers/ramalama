import logging
import sys

from ramalama.log_levels import LogLevel, coerce_log_level

logger = logging.getLogger("ramalama")


def configure_logger(level: LogLevel | str | int = LogLevel.WARNING) -> None:
    global logger

    resolved_level = coerce_log_level(level)
    lvl_value = int(resolved_level)

    logger.setLevel(lvl_value)
    logger.propagate = False

    fmt = "%(asctime)s - %(levelname)s - %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt)

    if not logger.handlers:
        logger.addHandler(logging.StreamHandler(sys.stderr))

    for handler in logger.handlers:
        handler.setLevel(lvl_value)
        handler.setFormatter(formatter)
