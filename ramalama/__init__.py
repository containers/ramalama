"""ramalama client module."""

import os
import sys

from ramalama.cli import HelpException, init_cli, print_version
from ramalama.common import apple_vm, perror
from ramalama.config import CONFIG

assert sys.version_info >= (3, 10), "Python 3.10 or greater is required."


def initialize_environment():
    # CONFIG.engine is pulled both from the environment and file configs
    if CONFIG.engine is not None and os.path.basename(CONFIG.engine) == "podman" and sys.platform == "darwin":
        run_with_podman_engine = apple_vm(CONFIG.engine, CONFIG)
        if not run_with_podman_engine and not CONFIG.is_set("engine"):
            CONFIG.engine = None


initialize_environment()


__all__ = ["perror", "init_cli", "print_version", "HelpException"]
