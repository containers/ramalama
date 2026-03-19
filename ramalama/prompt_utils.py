import os
import platform

from ramalama.config import ActiveConfig
from ramalama.console import EMOJI


def default_prefix() -> str:
    if not EMOJI:
        return "> "

    config = ActiveConfig()
    if config.prefix:
        return config.prefix

    if platform.system() == "Darwin":
        return "🍏 > "

    engine = config.engine
    if engine:
        engine_name = os.path.basename(engine)
        if engine_name == "podman":
            return "\U0001f9ad > "
        if engine_name == "docker":
            return "\U0001f40b > "

    return "\U0001f999 > "
