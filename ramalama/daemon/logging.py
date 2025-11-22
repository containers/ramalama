import logging
import os

from ramalama.log_levels import LogLevel

DEFAULT_LOG_DIR = "/var/tmp"

# Global logger
logger = logging.getLogger("ramalama-daemon")


def configure_logger(lvl: LogLevel = LogLevel.WARNING, log_file: str = DEFAULT_LOG_DIR) -> None:
    if logger.hasHandlers():
        return

    logger.setLevel(lvl)

    fmt = "%(asctime)s - %(levelname)s - %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt)

    log_file_path = os.path.join(log_file, "ramalama-daemon.log")
    handler = logging.FileHandler(log_file_path)
    handler.setLevel(lvl)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
