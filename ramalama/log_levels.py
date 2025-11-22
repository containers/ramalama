import logging
from enum import IntEnum
from typing import Union


class LogLevel(IntEnum):
    DEBUG = getattr(logging, "DEBUG")
    INFO = getattr(logging, "INFO")
    WARNING = getattr(logging, "WARNING")
    ERROR = getattr(logging, "ERROR")
    CRITICAL = getattr(logging, "CRITICAL")


def coerce_log_level(level: Union["LogLevel", str, int]) -> LogLevel:
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
