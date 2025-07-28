from dataclasses import dataclass, field

import pytest

from ramalama.model_store.snapshot_file import SnapshotFile
from ramalama.url import URL


@dataclass
class Input:
    Model: str


@dataclass
class Expected:
    URLList: list[str] = field(default_factory=lambda: [])
    Names: list[str] = field(default_factory=lambda: [])


@pytest.mark.parametrize(
    "input,expected",
    [
        (Input(""), Expected()),
        (Input("file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf"), Expected()),
        (
            Input(
                "huggingface.co/unsloth/Qwen3-Coder-480B-A35B-Instruct-GGUF/resolve/main/Q3_K_M/Qwen3-Coder-480B-A35B-Instruct-Q3_K_M-00001-of-00005.gguf"  # noqa: E501
            ),
            Expected(
                URLList=[
                    "https://huggingface.co/unsloth/Qwen3-Coder-480B-A35B-Instruct-GGUF/resolve/main/Q3_K_M/Qwen3-Coder-480B-A35B-Instruct-Q3_K_M-00001-of-00005.gguf",  # noqa: E501
                    "https://huggingface.co/unsloth/Qwen3-Coder-480B-A35B-Instruct-GGUF/resolve/main/Q3_K_M/Qwen3-Coder-480B-A35B-Instruct-Q3_K_M-00002-of-00005.gguf",  # noqa: E501
                    "https://huggingface.co/unsloth/Qwen3-Coder-480B-A35B-Instruct-GGUF/resolve/main/Q3_K_M/Qwen3-Coder-480B-A35B-Instruct-Q3_K_M-00003-of-00005.gguf",  # noqa: E501
                    "https://huggingface.co/unsloth/Qwen3-Coder-480B-A35B-Instruct-GGUF/resolve/main/Q3_K_M/Qwen3-Coder-480B-A35B-Instruct-Q3_K_M-00004-of-00005.gguf",  # noqa: E501
                    "https://huggingface.co/unsloth/Qwen3-Coder-480B-A35B-Instruct-GGUF/resolve/main/Q3_K_M/Qwen3-Coder-480B-A35B-Instruct-Q3_K_M-00005-of-00005.gguf",  # noqa: E501
                ],
                Names=[
                    "Qwen3-Coder-480B-A35B-Instruct-Q3_K_M-00001-of-00005.gguf",
                    "Qwen3-Coder-480B-A35B-Instruct-Q3_K_M-00002-of-00005.gguf",
                    "Qwen3-Coder-480B-A35B-Instruct-Q3_K_M-00003-of-00005.gguf",
                    "Qwen3-Coder-480B-A35B-Instruct-Q3_K_M-00004-of-00005.gguf",
                    "Qwen3-Coder-480B-A35B-Instruct-Q3_K_M-00005-of-00005.gguf",
                ],
            ),
        ),
    ],
)
def test__assemble_split_file_list(input: Input, expected: Expected):
    # store path and scheme irrelevant here
    model = URL(input.Model, "/store", "https")
    files: list[SnapshotFile] = model._assemble_split_file_list("doesnotmatterhere")
    file_count = len(files)
    assert file_count == len(expected.Names)
    assert file_count == len(expected.URLList)

    for i in range(file_count):
        assert files[i].url == expected.URLList[i]
        assert files[i].name == expected.Names[i]
