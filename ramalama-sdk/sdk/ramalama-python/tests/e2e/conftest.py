import pytest
from ramalama.config import CONFIG as ramalama_conf


def has_container_runtime() -> bool:
    return ramalama_conf.engine is not None


requires_container = pytest.mark.skipif(
    not has_container_runtime(),
    reason="No container runtime (docker/podman) available",
)


@pytest.fixture
def small_model():
    """A small model suitable for integration testing."""
    return "hf://ggml-org/SmolVLM-500M-Instruct-GGUF"
