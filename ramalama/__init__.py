"""ramalama client module."""

from ramalama.common import container_manager, exec_cmd, perror
from ramalama.cli import create_store, funcDict, usage
from ramalama.version import __version__
import subprocess
import sys
import os
import shutil

assert sys.version_info >= (3, 6), "Python 3.6 or greater is required."


__all__ = ['container_manager', 'create_store', 'perror',
           'funcDict', 'usage', '__version__', 'exec_cmd']
