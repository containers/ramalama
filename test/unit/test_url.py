import os
from dataclasses import dataclass, field

import pytest

from ramalama.model_store.snapshot_file import SnapshotFile
from ramalama.transports.url import URL, LocalModelFile


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


def test_local_model_file_uses_hardlink(tmp_path):
    """Test that LocalModelFile.download() uses hardlink instead of copy to save disk space."""
    # Create a test model file
    src_file = tmp_path / "test_model.gguf"
    src_file.write_text("test model content")

    dest_file = tmp_path / "dest_model.gguf"

    # Create LocalModelFile and download
    lmf = LocalModelFile(
        url=str(src_file),
        header={},
        model_file_hash="test_hash",
        name="test_model.gguf",
    )
    lmf.download(str(dest_file), str(tmp_path))

    # Verify files are hardlinked (same inode means no disk space duplication)
    src_stat = os.stat(src_file)
    dest_stat = os.stat(dest_file)

    assert src_stat.st_ino == dest_stat.st_ino, "Files should be hardlinked (same inode)"
    assert src_stat.st_nlink == 2, "Should have 2 links to the same inode"
    assert dest_file.read_text() == "test model content", "Content should be accessible"
