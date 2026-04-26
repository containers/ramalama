"""Shim for setuptools < 61 (e.g. CentOS/RHEL 9) which cannot read PEP 621 [project] metadata.

Newer setuptools (>= 61) reads pyproject.toml directly and ignores this file.
"""

import glob
import re

from setuptools import find_packages, setup

# Read version without importing ramalama (it may not be installable yet)
_version_match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', open("ramalama/version.py").read(), re.MULTILINE)
if not _version_match:
    raise RuntimeError("Unable to find __version__ in ramalama/version.py")
__version__ = _version_match.group(1)

setup(
    name="ramalama",
    version=__version__,
    description="RamaLama is a command line tool for working with AI LLM models.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    license="MIT",
    python_requires=">=3.9",
    install_requires=[
        "argcomplete",
        "jinja2",
        "pyyaml",
    ],
    packages=find_packages(include=["ramalama", "ramalama.*"]),
    include_package_data=True,
    package_data={"ramalama": ["py.typed"]},
    entry_points={
        "console_scripts": [
            "ramalama = ramalama.cli:main",
        ],
        "ramalama.runtimes.v1alpha": [
            "llama.cpp = ramalama.plugins.runtimes.inference.llama_cpp:LlamaCppPlugin",
            "vllm = ramalama.plugins.runtimes.inference.vllm:VllmPlugin",
            "mlx = ramalama.plugins.runtimes.inference.mlx:MlxPlugin",
        ],
    },
    data_files=[
        ("share/ramalama", ["shortnames/shortnames.conf", "docs/ramalama.conf"]),
        ("share/man/man1", glob.glob("docs/*.1")),
        ("share/man/man5", glob.glob("docs/*.5")),
        ("share/man/man7", glob.glob("docs/*.7")),
        ("share/bash-completion/completions", glob.glob("completions/bash-completion/completions/*")),
        ("share/zsh/site-functions", glob.glob("completions/zsh/site-functions/*")),
        ("share/fish/vendor_completions.d", glob.glob("completions/fish/vendor_completions.d/*")),
    ],
)
