import os
import sys
import locale
import logging

def is_locale_utf8():
    """Check if the system locale is UTF-8."""
    return 'UTF-8' in os.getenv('LC_CTYPE', '') or 'UTF-8' in os.getenv('LANG', '')

def supports_emoji():
    """Detect if the terminal supports emoji output."""
    term = os.getenv("TERM")
    if not term or term in ("dumb", "linux"):
        return False

    return is_locale_utf8()

# Allow users to override emoji support via an environment variable
# If RAMALAMA_FORCE_EMOJI is not set, it defaults to checking supports_emoji()
RAMALAMA_FORCE_EMOJI = os.getenv("RAMALAMA_FORCE_EMOJI")
FORCE_EMOJI = RAMALAMA_FORCE_EMOJI.lower() == "true" if RAMALAMA_FORCE_EMOJI else None
EMOJI = FORCE_EMOJI if FORCE_EMOJI is not None else supports_emoji()

# Define emoji-aware logging messages
def error(msg):
    formatted_msg = f"❌ {msg}" if EMOJI else f"[ERROR] {msg}"
    logging.error(formatted_msg)

def warning(msg):
    formatted_msg = f"⚠️  {msg}" if EMOJI else f"[WARNING] {msg}"
    logging.warning(formatted_msg)

def info(msg):
    formatted_msg = f"ℹ️  {msg}" if EMOJI else f"[INFO] {msg}"
    logging.info(formatted_msg)
