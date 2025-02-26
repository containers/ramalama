from dataclasses import dataclass
from typing import Union

import pytest

from ramalama.huggingface import Huggingface
from ramalama.model_factory import ModelFactory
from ramalama.oci import OCI
from ramalama.ollama import Ollama
from ramalama.url import URL


@dataclass
class Input:
    Model: str
    Transport: str
    Engine: str


@pytest.mark.parametrize(
    "input,expected,error",
    [
        (Input("", "", ""), None, KeyError),
        (Input("huggingface://granite-code", "", ""), Huggingface, None),
        (Input("hf://granite-code", "", ""), Huggingface, None),
        (Input("hf.co/granite-code", "", ""), Huggingface, None),
        (Input("ollama://granite-code", "", ""), Ollama, None),
        (Input("ollama.com/library/granite-code", "", ""), Ollama, None),
        (Input("oci://granite-code", "", "podman"), OCI, None),
        (Input("docker://granite-code", "", "podman"), OCI, None),
        (
            Input(
                "http://huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf",
                "",
                "",
            ),
            URL,
            None,
        ),
        (
            Input(
                "https://huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf",
                "",
                "",
            ),
            URL,
            None,
        ),
        (Input("file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf", "", ""), URL, None),
        (Input("granite-code", "huggingface", ""), Huggingface, None),
        (Input("granite-code", "ollama", ""), Ollama, None),
        (Input("granite-code", "oci", ""), OCI, None),
    ],
)
def test_model_factory_create(input: Input, expected: type[Union[Huggingface, Ollama, URL, OCI]], error):
    if error is not None:
        with pytest.raises(error):
            ModelFactory(input.Model, input.Transport, input.Engine).create()
    else:
        model = ModelFactory(input.Model, input.Transport, input.Engine).create()
        assert isinstance(model, expected)


@pytest.mark.parametrize(
    "input,error",
    [
        (Input("", "", ""), None),
        (Input("oci://granite-code", "", "podman"), None),
        (Input("docker://granite-code", "", "podman"), None),
        (Input("file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf", "", ""), ValueError),
        (Input("huggingface://granite-code", "", ""), ValueError),
        (Input("hf://granite-code", "", ""), ValueError),
        (Input("hf.co/granite-code", "", ""), None),
        (Input("ollama://granite-code", "", ""), ValueError),
        (Input("ollama.com/library/granite-code", "", ""), None),
        (Input("granite-code", "", ""), None),
    ],
)
def test_validate_oci_model_input(input: Input, error):
    if error is not None:
        with pytest.raises(error):
            ModelFactory(input.Model, input.Transport, input.Engine).validate_oci_model_input()
        return

    ModelFactory(input.Model, input.Transport, input.Engine).validate_oci_model_input()


@pytest.mark.parametrize(
    "input,cls,expected",
    [
        (Input("huggingface://granite-code", "", ""), Huggingface, "granite-code"),
        (
            Input("huggingface://ibm-granite/granite-3b-code-base-2k-GGUF/granite-code", "", ""),
            Huggingface,
            "ibm-granite/granite-3b-code-base-2k-GGUF/granite-code",
        ),
        (Input("hf://granite-code", "", ""), Huggingface, "granite-code"),
        (Input("hf.co/granite-code", "", ""), Huggingface, "granite-code"),
        (Input("ollama://granite-code", "", ""), Ollama, "granite-code"),
        (Input("ollama.com/library/granite-code", "", ""), Ollama, "granite-code"),
        (
            Input("ollama.com/library/ibm-granite/granite-3b-code-base-2k-GGUF/granite-code", "", ""),
            Ollama,
            "ibm-granite/granite-3b-code-base-2k-GGUF/granite-code",
        ),
        (Input("oci://granite-code", "", "podman"), OCI, "granite-code"),
        (Input("docker://granite-code", "", "podman"), OCI, "granite-code"),
        (
            Input(
                "http://huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf",
                "",
                "",
            ),
            URL,
            "huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf",
        ),
        (
            Input(
                "https://huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf",
                "",
                "",
            ),
            URL,
            "huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf",
        ),
        (
            Input("file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf", "", ""),
            URL,
            "/tmp/models/granite-3b-code-base.Q4_K_M.gguf",
        ),
        (Input("granite-code", "huggingface", ""), Huggingface, "granite-code"),
        (Input("granite-code", "ollama", ""), Ollama, "granite-code"),
        (Input("granite-code", "oci", ""), OCI, "granite-code"),
    ],
)
def test_prune_model_input(input: Input, cls: type[Union[Huggingface, Ollama, URL, OCI]], expected: str):
    pruned_model_input = ModelFactory(input.Model, input.Transport, input.Engine).prune_model_input(cls)
    assert pruned_model_input == expected
