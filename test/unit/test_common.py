import pytest

from ramalama.common import rm_until_substring

@pytest.mark.parametrize(
        "input,rm_until,expected", 
        [
            ("", "", ""),
            ("huggingface://granite-code", "://", "granite-code"),
            ("hf://granite-code", "://", "granite-code"),
            ("hf.co/granite-code", "hf.co/", "granite-code"),
            ("http://huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf", ".co/", "ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf"),
            ("file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf", "", "file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf"),
        ]
)
def test_rm_until_substring(input: str, rm_until: str, expected: str):
    actual = rm_until_substring(input, rm_until)
    assert actual == expected
