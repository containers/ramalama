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
    UseModelStore: bool
    Transport: str
    Engine: str


hf_granite_blob = "https://huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob"


@pytest.mark.parametrize(
    "input,expected,error",
    [
        (Input("", False, "", ""), None, KeyError),
        (Input("huggingface://granite-code", False, "", ""), Huggingface, None),
        (Input("hf://granite-code", False, "", ""), Huggingface, None),
        (Input("hf.co/granite-code", False, "", ""), Huggingface, None),
        (Input("ollama://granite-code", False, "", ""), Ollama, None),
        (Input("ollama.com/library/granite-code", False, "", ""), Ollama, None),
        (Input("oci://granite-code", False, "", "podman"), OCI, None),
        (Input("docker://granite-code", False, "", "podman"), OCI, None),
        (
            Input(
                f"{hf_granite_blob}/main/granite-3b-code-base.Q4_K_M.gguf",
                False,
                "",
                "",
            ),
            URL,
            None,
        ),
        (
            Input(
                f"{hf_granite_blob}/main/granite-3b-code-base.Q4_K_M.gguf",
                False,
                "",
                "",
            ),
            URL,
            None,
        ),
        (Input("file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf", False, "", ""), URL, None),
        (Input("granite-code", False, "huggingface", ""), Huggingface, None),
        (Input("granite-code", False, "ollama", ""), Ollama, None),
        (Input("granite-code", False, "oci", ""), OCI, None),
    ],
)
def test_model_factory_create(input: Input, expected: type[Union[Huggingface, Ollama, URL, OCI]], error):
    if error is not None:
        with pytest.raises(error):
            ModelFactory(input.Model, "/tmp/store", input.UseModelStore, input.Transport, input.Engine).create()
    else:
        model = ModelFactory(input.Model, "/tmp/store", input.UseModelStore, input.Transport, input.Engine).create()
        assert isinstance(model, expected)


@pytest.mark.parametrize(
    "input,error",
    [
        (Input("", False, "", ""), KeyError),
        (Input("oci://granite-code", False, "", "podman"), None),
        (Input("docker://granite-code", False, "", "podman"), None),
        (Input("file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf", False, "", ""), ValueError),
        (Input("huggingface://granite-code", False, "", ""), ValueError),
        (Input("hf://granite-code", False, "", ""), ValueError),
        (Input("hf.co/granite-code", False, "", ""), None),
        (Input("ollama://granite-code", False, "", ""), ValueError),
        (Input("ollama.com/library/granite-code", False, "", ""), None),
        (Input("granite-code", False, "ollama", ""), None),
        (Input("granite-code", False, "", ""), KeyError),
    ],
)
def test_validate_oci_model_input(input: Input, error):
    if error is not None:
        with pytest.raises(error):
            ModelFactory(input.Model, "/tmp/store", input.Transport, input.Engine).validate_oci_model_input()
        return

    ModelFactory(
        input.Model, "/tmp/store", input.UseModelStore, input.Transport, input.Engine
    ).validate_oci_model_input()


@pytest.mark.parametrize(
    "input,expected",
    [
        (Input("huggingface://granite-code", False, "", ""), "granite-code"),
        (
            Input("huggingface://ibm-granite/granite-3b-code-base-2k-GGUF/granite-code", False, "", ""),
            "ibm-granite/granite-3b-code-base-2k-GGUF/granite-code",
        ),
        (Input("hf://granite-code", False, "", ""), "granite-code"),
        (Input("hf.co/granite-code", False, "", ""), "granite-code"),
        (Input("ollama://granite-code", False, "", ""), "granite-code"),
        (Input("ollama.com/library/granite-code", False, "", ""), "granite-code"),
        (
            Input("ollama.com/library/ibm-granite/granite-3b-code-base-2k-GGUF/granite-code", False, "", ""),
            "ibm-granite/granite-3b-code-base-2k-GGUF/granite-code",
        ),
        (Input("oci://granite-code", False, "", "podman"), "granite-code"),
        (Input("docker://granite-code", False, "", "podman"), "granite-code"),
        (
            Input(
                f"{hf_granite_blob}/main/granite-3b-code-base.Q4_K_M.gguf",
                False,
                "",
                "",
            ),
            "huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf",
        ),
        (
            Input(
                f"{hf_granite_blob}/main/granite-3b-code-base.Q4_K_M.gguf",
                False,
                "",
                "",
            ),
            "huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf",
        ),
        (
            Input("file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf", False, "", ""),
            "/tmp/models/granite-3b-code-base.Q4_K_M.gguf",
        ),
        (Input("granite-code", False, "huggingface", ""), "granite-code"),
        (Input("granite-code", False, "ollama", ""), "granite-code"),
        (Input("granite-code", False, "oci", ""), "granite-code"),
    ],
)
def test_prune_model_input(input: Input, expected: str):
    pruned_model_input = ModelFactory(
        input.Model, "/tmp/store", input.UseModelStore, input.Transport, input.Engine
    ).prune_model_input()
    assert pruned_model_input == expected
