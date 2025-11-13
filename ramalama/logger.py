import logging
import sys

from ramalama.daemon.logging import LogLevel

logger = logging.getLogger("ramalama")


def _coerce_log_level(level: LogLevel | str | int) -> LogLevel:
    if isinstance(level, LogLevel):
        return level
    if isinstance(level, str):
        try:
            return LogLevel[level.upper()]
        except KeyError as exc:
            raise ValueError(f"Unsupported log level: {level}") from exc
    if isinstance(level, int):
        try:
            return LogLevel(level)
        except ValueError as exc:
            raise ValueError(f"Unsupported log level value: {level}") from exc
    raise TypeError(f"Cannot coerce {level!r} to LogLevel")


def configure_logger(level: LogLevel | str = LogLevel.WARNING) -> None:
    global logger

    resolved_level = _coerce_log_level(level)
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
