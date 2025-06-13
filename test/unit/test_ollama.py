from unittest.mock import patch

import pytest

from ramalama.arg_types import StoreArgs
from ramalama.ollama import Ollama, OllamaRepository


@pytest.fixture
def ollama_model():
    return Ollama("llama2:7b")


@pytest.fixture
def ollama_repository():
    return OllamaRepository("ollama", "http://localhost:11434", "http://localhost:11434/blobs")


@pytest.fixture
def args():
    return StoreArgs(store="/var/lib/ramalama", use_model_store=True, engine="podman", container=True)


def test_ollama_model_initialization(ollama_model):
    assert ollama_model.model == "llama2:7b"
    assert ollama_model.type == "Ollama"


def test_ollama_model_local_path(ollama_model, args):
    model_path, models, model_base, model_name, model_tag = ollama_model._local(args)
    assert model_path == "/var/lib/ramalama/models/ollama/llama2:7b"
    assert models == "/var/lib/ramalama/models/ollama"
    assert model_base == "llama2"
    assert model_name == "library/llama2"
    assert model_tag == "7b"


def test_ollama_model_exists(ollama_model, args):
    with patch("os.path.exists", return_value=True):
        assert ollama_model.exists(args) is not None

    with patch("os.path.exists", return_value=False):
        assert ollama_model.exists(args) is None


def test_ollama_model_path(ollama_model, args):
    with patch("os.path.exists", return_value=True):
        assert ollama_model.path(args) == "/var/lib/ramalama/models/ollama/llama2:7b"


def test_ollama_model_pull(ollama_model, args):
    args.quiet = True
    with patch("os.path.exists", return_value=False):
        with patch("ramalama.ollama.repo_pull", return_value="/tmp") as mock_pull:
            ollama_model.pull(args)
            mock_pull.assert_called_once()
