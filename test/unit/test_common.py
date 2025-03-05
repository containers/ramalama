import os
from pathlib import Path

import pytest

from ramalama.common import rm_until_substring, verify_checksum


@pytest.mark.parametrize(
    "input,rm_until,expected",
    [
        ("", "", ""),
        ("huggingface://granite-code", "://", "granite-code"),
        ("hf://granite-code", "://", "granite-code"),
        ("hf.co/granite-code", "hf.co/", "granite-code"),
        (
            "http://huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf",
            ".co/",
            "ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf",
        ),
        (
            "file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf",
            "",
            "file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf",
        ),
    ],
)
def test_rm_until_substring(input: str, rm_until: str, expected: str):
    actual = rm_until_substring(input, rm_until)
    assert actual == expected


@pytest.mark.parametrize(
    "input_file,expected_error,expected_result",
    [
        ("", ValueError, None),
        ("invalidname", ValueError, None),
        ("sha256:123", ValueError, None),
        ("sha256:62fbfd9ed093d6e5ac83190c86eec5369317919f4b149598d2dbb38900e9faef", None, True),
        ("sha256-62fbfd9ed093d6e5ac83190c86eec5369317919f4b149598d2dbb38900e9faef", None, True),
        ("sha256:16cd1aa2bd52b0e87ff143e8a8a7bb6fcb0163c624396ca58e7f75ec99ef081f", None, False),
    ],
)
def test_verify_checksum(input_file: str, expected_error: Exception, expected_result: bool):
    full_path = os.path.join(Path(__file__).parent, "data", "verify_checksum", input_file)

    if expected_error is None:
        assert verify_checksum(full_path) == expected_result
        return

    with pytest.raises(expected_error):
        verify_checksum(full_path)
