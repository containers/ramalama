from unittest.mock import patch

import pytest

from ramalama.arg_types import StoreArgs
from ramalama.model_store.snapshot_file import LocalSnapshotFile, SnapshotFile, SnapshotFileType
from ramalama.ollama import Ollama, OllamaRepository


@pytest.fixture
def ollama_model(args: StoreArgs):
    return Ollama("llama2:7b", args.store)


@pytest.fixture
def args():
    return StoreArgs(store="/tmp/ramalama/store", engine="podman", container=True)


def test_ollama_model_initialization(ollama_model):
    assert ollama_model.model == "llama2:7b"
    assert ollama_model.type == "Ollama"


class OllamaRepositoryMock(OllamaRepository):

    def __init__(self, name):
        super().__init__(name)

    def fetch_manifest(self, tag: str):
        return {
            "layers": [
                {
                    "mediaType": "application/vnd.ollama.image.model",
                    "digest": "sha256-bf0ecbdb9b814248d086c9b69cf26182d9d4138f2ad3d0637c4555fc8cbf68e5",
                }
            ]
        }

    def get_file_list(self, tag, cached_files, is_model_in_ollama_cache, manifest=None) -> list[SnapshotFile]:
        return [LocalSnapshotFile("dummy content", "dummy", SnapshotFileType.Other)]


def test_ollama_model_pull(ollama_model, args):
    args.quiet = True
    with patch("ramalama.ollama.OllamaRepository", return_value=OllamaRepositoryMock("dummy-model")):
        ollama_model.pull(args)
