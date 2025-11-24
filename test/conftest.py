import os
import platform
import shutil
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

skip_if_no_huggingface_cli = pytest.mark.skipif(shutil.which("hf") is None, reason="hf cli not installed")

skip_if_no_llama_bench = pytest.mark.skipif(shutil.which("llama-bench") is None, reason="llama-bench not installed")
