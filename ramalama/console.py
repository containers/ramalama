import os

from ramalama.logger import logger


def is_locale_utf8():
    """Check if the system locale is UTF-8."""
    return any('UTF-8' in os.getenv(var, '') for var in ['LC_ALL', 'LC_CTYPE', 'LANG'])


def supports_emoji():
    """Detect if the terminal supports emoji output."""
    term = os.getenv("TERM")
    if not term or term in ("dumb", "linux"):
        return False

    return is_locale_utf8()


# Allow users to override emoji support via an environment variable
# If RAMALAMA_FORCE_EMOJI is not set, it defaults to checking supports_emoji()
EMOJI = os.getenv("RAMALAMA_FORCE_EMOJI", '').lower() == "true" or supports_emoji()


# Define emoji-aware logging messages
def log_message(level, msg, emoji_msg):
    return f"{emoji_msg} {msg}" if EMOJI else f"{msg}"


def error(msg):
    logger.error(log_message("ERROR", msg, "❌"))


def warning(msg):
    logger.warning(log_message("WARNING", msg, "⚠️"))


def info(msg):
    logger.info(log_message("INFO", msg, "ℹ️"))
