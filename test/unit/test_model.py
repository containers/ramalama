import pytest

from ramalama.model_factory import ModelFactory

hf_granite_blob = "https://huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob"


@pytest.mark.parametrize(
    "model_input,expected_name,expected_tag,expected_orga",
    [
        ("huggingface://granite-code", "granite-code", "latest", ""),
        ("hf://granite-code", "granite-code", "latest", ""),
        (
            f"{hf_granite_blob}/main/granite-3b-code-base.Q4_K_M.gguf",
            "granite-3b-code-base.Q4_K_M.gguf",
            "main",
            "huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF",
        ),
        (
            f"{hf_granite_blob}/8ee52dc636b27b99caf046e717a87fb37ad9f33e/granite-3b-code-base.Q4_K_M.gguf",
            "granite-3b-code-base.Q4_K_M.gguf",
            "8ee52dc636b27b99caf046e717a87fb37ad9f33e",
            "huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF",
        ),
        ("ollama://granite-code", "granite-code", "latest", ""),
        (
            "https://ollama.com/huihui_ai/granite3.1-dense-abliterated:2b-instruct-fp16",
            "granite3.1-dense-abliterated",
            "2b-instruct-fp16",
            "ollama.com/huihui_ai",
        ),
        ("ollama.com/library/granite-code", "granite-code", "latest", ""),
        (
            "huihui_ai/granite3.1-dense-abliterated:2b-instruct-fp16",
            "granite3.1-dense-abliterated",
            "2b-instruct-fp16",
            "huihui_ai",
        ),
        ("oci://granite-code", "granite-code", "latest", ""),
        ("docker://granite-code", "granite-code", "latest", ""),
        ("docker://granite-code:v1.1.1", "granite-code", "v1.1.1", ""),
        (
            "file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf",
            "granite-3b-code-base.Q4_K_M.gguf",
            "latest",
            "tmp/models",
        ),
    ],
)
def test_extract_model_identifiers(model_input: str, expected_name: str, expected_tag: str, expected_orga: str):
    name, tag, orga = ModelFactory(model_input, "/tmp/store", False).create().extract_model_identifiers()
    assert name == expected_name
    assert tag == expected_tag
    assert orga == expected_orga
