"""ramalama client module."""

import os
import sys

from ramalama.cli import HelpException, init_cli, print_version
from ramalama.common import apple_vm, perror
from ramalama.config import CONFIG

assert sys.version_info >= (3, 10), "Python 3.10 or greater is required."

__all__ = ["perror", "init_cli", "print_version", "HelpException"]
