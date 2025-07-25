from pathlib import Path
from typing import Optional, Union

import pytest

from ramalama.huggingface import Huggingface
from ramalama.model_store.reffile import RefJSONFile, StoreFile, StoreFileType
from ramalama.model_store.store import ModelStore
from ramalama.oci import OCI
from ramalama.ollama import Ollama
from ramalama.url import URL


class Args:
    def __init__(
        self, type: str = "raw", gguf: Optional[str] = None, carimage: str = "quay.io/ramalama/ramalama-rag:latest"
    ):
        self.type = type
        self.carimage = carimage
        self.gguf = gguf


class Input:

    def __init__(
        self,
        source_model: Union[Ollama, URL, Huggingface],
        model_files: list[StoreFile] = [],
        args: Args = Args(),
    ):
        self.source_model = source_model
        self.model_files = model_files
        self.args = args


DATA_PATH = Path(__file__).parent / "data" / "test_oci"
STORE_PATH = "/store"


@pytest.mark.parametrize(
    "input,expected_file_path",
    [
        (
            Input(
                source_model=URL("/Users/rmajadas/src/redhat/ramalama/aimodel", STORE_PATH, "file://"),
                model_files=[
                    StoreFile(
                        "sha256-cfe21da457a108815d015dff95bed59c34a6f170fde7e4f99fa0c3f809251df3",
                        "aimodel",
                        StoreFileType.OTHER,
                    ),
                ],
            ),
            DATA_PATH / "url-simple",
        ),
        (
            Input(
                source_model=Ollama("tinyllama/tinyllama", STORE_PATH),
                model_files=[
                    StoreFile(
                        "sha256-2af3b81862c6be03c769683af18efdadb2c33f60ff32ab6f83e42c043d6c7816",
                        "tinyllama",
                        StoreFileType.OTHER,
                    ),
                    StoreFile(
                        "sha256-6331358be52a6ebc2fd0755a51ad1175734fd17a628ab5ea6897109396245362",
                        "config.json",
                        StoreFileType.OTHER,
                    ),
                    StoreFile(
                        "sha256-af0ddbdaaa26f30d54d727f9dd944b76bdb926fdaf9a58f63f78c532f57c191f",
                        "chat_template",
                        StoreFileType.OTHER,
                    ),
                    StoreFile(
                        "sha256-d9c61d99be002196cfaa025ab517dc149ec1894f0bbb56195aee86853299fa01",
                        "chat_template_converted",
                        StoreFileType.OTHER,
                    ),
                ],
                args=Args(gguf="Q3_K_S"),
            ),
            DATA_PATH / "ollama-gguf",
        ),
        (
            Input(
                source_model=Ollama("tinyllama/tinyllama", STORE_PATH),
                model_files=[
                    StoreFile(
                        "sha256-2af3b81862c6be03c769683af18efdadb2c33f60ff32ab6f83e42c043d6c7816",
                        "tinyllama",
                        StoreFileType.OTHER,
                    ),
                    StoreFile(
                        "sha256-6331358be52a6ebc2fd0755a51ad1175734fd17a628ab5ea6897109396245362",
                        "config.json",
                        StoreFileType.OTHER,
                    ),
                    StoreFile(
                        "sha256-af0ddbdaaa26f30d54d727f9dd944b76bdb926fdaf9a58f63f78c532f57c191f",
                        "chat_template",
                        StoreFileType.OTHER,
                    ),
                    StoreFile(
                        "sha256-d9c61d99be002196cfaa025ab517dc149ec1894f0bbb56195aee86853299fa01",
                        "chat_template_converted",
                        StoreFileType.OTHER,
                    ),
                ],
                args=Args(type="car"),
            ),
            DATA_PATH / "ollama-type-car",
        ),
        (
            Input(
                source_model=Ollama("tinyllama/tinyllama", STORE_PATH),
                model_files=[
                    StoreFile(
                        "sha256-2af3b81862c6be03c769683af18efdadb2c33f60ff32ab6f83e42c043d6c7816",
                        "tinyllama",
                        StoreFileType.OTHER,
                    ),
                    StoreFile(
                        "sha256-6331358be52a6ebc2fd0755a51ad1175734fd17a628ab5ea6897109396245362",
                        "config.json",
                        StoreFileType.OTHER,
                    ),
                    StoreFile(
                        "sha256-af0ddbdaaa26f30d54d727f9dd944b76bdb926fdaf9a58f63f78c532f57c191f",
                        "chat_template",
                        StoreFileType.OTHER,
                    ),
                    StoreFile(
                        "sha256-d9c61d99be002196cfaa025ab517dc149ec1894f0bbb56195aee86853299fa01",
                        "chat_template_converted",
                        StoreFileType.OTHER,
                    ),
                ],
                args=Args(type="car", gguf="Q3_K_L"),
            ),
            DATA_PATH / "ollama-type-car-gguf",
        ),
    ],
)
def test__generate_containerfile(input: Input, expected_file_path: Path, monkeypatch):
    oci = OCI("custom-container", STORE_PATH, "podman")

    # mocking the reffile from store and setting the gguf attribute
    monkeypatch.setattr(
        ModelStore,
        "get_ref_file",
        lambda self, ret: RefJSONFile("hash-doesntmatter", "path-doesntmatter", input.model_files),
    )

    file = oci._generate_containerfile(input.source_model, input.args)
    with open(expected_file_path, "r") as expected_file:
        assert file == expected_file.read()
