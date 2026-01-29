import importlib.util
import os
import platform
import shutil
import subprocess
import sys

import pytest

ramalama_container = True
ramalama_container_engine = "podman"


def pytest_addoption(parser):
    container_group = parser.getgroup("container")
    container_group.addoption(
        "--container",
        action="store_true",
        dest="container",
        default=True,
        help="Enable container mode",
    )
    container_group.addoption(
        "--no-container",
        action="store_false",
        dest="container",
        help="Disable container mode",
    )
    container_group.addoption(
        "--container-engine",
        action="store",
        choices=["podman", "docker"],
        default="podman",
        help="Container engine to use",
    )


def pytest_configure(config):
    global ramalama_container
    global ramalama_container_engine
    ramalama_container = config.option.container
    ramalama_container_engine = config.option.container_engine


@pytest.fixture()
def is_container(request):
    return ramalama_container


@pytest.fixture()
def container_engine(request):
    return ramalama_container_engine


@pytest.fixture(scope="session")
def test_model():
    # Use different models for little-endian (e.g. x86_64, aarch64) and
    # big-endian (e.g. s390x) architectures.
    return "smollm:135m" if sys.byteorder == "little" else "stories-be:260k"


def get_podman_version():
    """Get podman version as a tuple of integers (major, minor, patch)."""
    try:
        result = subprocess.run(
            ["podman", "version", "--format", "{{.Client.Version}}"], capture_output=True, text=True, check=True
        )
        version_str = result.stdout.strip()
        # Handle versions like "5.7.0-dev" by taking only the numeric part
        version_parts = version_str.split('-')[0].split('.')
        return tuple(int(x) for x in version_parts[:3])
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return (0, 0, 0)


def is_podman_version_at_least(major, minor, patch=0):
    """Check if podman version is at least the specified version."""
    current = get_podman_version()
    required = (major, minor, patch)
    return current >= required


skip_if_no_container = pytest.mark.skipif("not config.option.container", reason="no container mode is enabled")
skip_if_container = pytest.mark.skipif("config.option.container", reason="container mode is enabled")
skip_if_docker = pytest.mark.skipif(
    "config.option.container_engine == 'docker'", reason="docker is the container engine"
)

skip_if_darwin = pytest.mark.skipif(platform.system() == "Darwin", reason="Darwin operating system")
skip_if_not_darwin = pytest.mark.skipif(platform.system() != "Darwin", reason="not Darwin operating system")
skip_if_gh_actions_darwin = pytest.mark.skipif(
    platform.system() == "Darwin" and os.getenv("GITHUB_ACTIONS") == "true",
    reason="GitHub Actions Darwin has not container support",
)

skip_if_windows = pytest.mark.skipif(platform.system() == "Windows", reason="Windows operating system")
skip_if_not_windows = pytest.mark.skipif(platform.system() != "Windows", reason="not Windows operating system")

skip_if_no_llama_bench = pytest.mark.skipif(shutil.which("llama-bench") is None, reason="llama-bench not installed")

skip_if_no_mlx = pytest.mark.skipif(
    importlib.util.find_spec("mlx_lm") is None, reason="MLX runtime requires mlx-lm package to be installed"
)

IS_APPLE_SILICON = platform.system() == "Darwin" and platform.machine() == "arm64"
skip_if_apple_silicon = pytest.mark.skipif(IS_APPLE_SILICON, reason="Apple Silicon")
skip_if_not_apple_silicon = pytest.mark.skipif(not IS_APPLE_SILICON, reason="not Apple Silicon")

xfail_if_windows = pytest.mark.xfail(
    platform.system() == "Windows",
    reason="Known failure on Windows",
)

skip_if_no_ollama = pytest.mark.skipif(shutil.which("ollama") is None, reason="ollama not installed")

skip_if_big_endian_machine = pytest.mark.skipif(sys.byteorder == "big", reason="skip big-endian architecture")
skip_if_little_endian_machine = pytest.mark.skipif(sys.byteorder == "little", reason="skip little-endian architecture")
skip_if_ppc64le = pytest.mark.skipif(platform.machine() == "ppc64le", reason="skip on ppc64le")
skip_if_s390x = pytest.mark.skipif(platform.machine() == "s390x", reason="skip on s390x")

skip_if_podman_too_old = pytest.mark.skipif(
    not is_podman_version_at_least(5, 7, 0), reason="requires podman >= 5.7.0 for artifact support"
)
