"""ramalama client module."""

import sys

from ramalama import cli
from ramalama.cli import HelpException, init_cli, print_version
from ramalama.common import perror

assert sys.version_info >= (3, 10), "Python 3.10 or greater is required."

__all__ = ["cli", "perror", "init_cli", "print_version", "HelpException"]
