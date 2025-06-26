from dataclasses import dataclass
from typing import Union

import pytest

from ramalama.huggingface import Huggingface
from ramalama.model_factory import ModelFactory
from ramalama.modelscope import ModelScope
from ramalama.oci import OCI
from ramalama.ollama import Ollama
from ramalama.url import URL


@dataclass
class Input:
    Model: str
    Transport: str
    Engine: str


class ARGS:
    store = "/tmp/store"
    engine = ""
    container = True

    def __init__(self, engine=""):
        self.engine = engine


hf_granite_blob = "https://huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob"


@pytest.mark.parametrize(
    "input,expected,error",
    [
        (Input("", "", ""), None, KeyError),
        (Input("huggingface://granite-code", "", ""), Huggingface, None),
        (Input("hf://granite-code", "", ""), Huggingface, None),
        (Input("hf.co/granite-code", "", ""), Huggingface, None),
        (Input("modelscope://granite-code", "", ""), ModelScope, None),
        (Input("ms://granite-code", "", ""), ModelScope, None),
        (Input("ollama://granite-code", "", ""), Ollama, None),
        (Input("ollama.com/library/granite-code", "", ""), Ollama, None),
        (Input("oci://granite-code", "", "podman"), OCI, None),
        (Input("docker://granite-code", "", "podman"), OCI, None),
        (
            Input(
                f"{hf_granite_blob}/main/granite-3b-code-base.Q4_K_M.gguf",
                "",
                "",
            ),
            URL,
            None,
        ),
        (
            Input(
                f"{hf_granite_blob}/main/granite-3b-code-base.Q4_K_M.gguf",
                "",
                "",
            ),
            URL,
            None,
        ),
        (Input("file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf", "", ""), URL, None),
        (Input("granite-code", "huggingface", ""), Huggingface, None),
        (Input("granite-code", "ollama", ""), Ollama, None),
        (Input("granite-code", "oci", ""), OCI, ValueError),
    ],
)
def test_model_factory_create(input: Input, expected: type[Union[Huggingface, Ollama, URL, OCI]], error):
    args = ARGS(input.Engine)

    if error is not None:
        with pytest.raises(error):
            ModelFactory(input.Model, args, input.Transport).create()
    else:
        model = ModelFactory(input.Model, args, input.Transport).create()
        assert isinstance(model, expected)


@pytest.mark.parametrize(
    "input,error",
    [
        (Input("", "", ""), KeyError),
        (Input("oci://granite-code", "", "podman"), None),
        (Input("docker://granite-code", "", "podman"), None),
        (Input("file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf", "", ""), ValueError),
        (Input("huggingface://granite-code", "", ""), ValueError),
        (Input("hf://granite-code", "", ""), ValueError),
        (Input("hf.co/granite-code", "", ""), None),
        (Input("modelscope://granite-code", "", ""), ValueError),
        (Input("ms://granite-code", "", ""), ValueError),
        (Input("ollama://granite-code", "", ""), ValueError),
        (Input("ollama.com/library/granite-code", "", ""), None),
        (Input("granite-code", "ollama", ""), None),
        (Input("granite-code", "", ""), KeyError),
    ],
)
def test_validate_oci_model_input(input: Input, error):
    args = ARGS(input.Engine)

    if error is not None:
        with pytest.raises(error):
            ModelFactory(input.Model, args, input.Transport).validate_oci_model_input()
        return

    ModelFactory(input.Model, args, input.Transport).validate_oci_model_input()


@pytest.mark.parametrize(
    "input,expected",
    [
        (Input("huggingface://granite-code", "", ""), "granite-code"),
        (
            Input("huggingface://ibm-granite/granite-3b-code-base-2k-GGUF/granite-code", "", ""),
            "ibm-granite/granite-3b-code-base-2k-GGUF/granite-code",
        ),
        (Input("hf://granite-code", "", ""), "granite-code"),
        (Input("hf.co/granite-code", "", ""), "granite-code"),
        (Input("modelscope://granite-code", "", ""), "granite-code"),
        (
            Input("modelscope://ibm-granite/granite-3b-code-base-2k-GGUF/granite-code", "", ""),
            "ibm-granite/granite-3b-code-base-2k-GGUF/granite-code",
        ),
        (Input("ms://granite-code", "", ""), "granite-code"),
        (Input("ollama://granite-code", "", ""), "granite-code"),
        (Input("ollama.com/library/granite-code", "", ""), "granite-code"),
        (
            Input("ollama.com/library/ibm-granite/granite-3b-code-base-2k-GGUF/granite-code", "", ""),
            "ibm-granite/granite-3b-code-base-2k-GGUF/granite-code",
        ),
        (Input("oci://granite-code", "", "podman"), "granite-code"),
        (Input("docker://granite-code", "", "podman"), "granite-code"),
        (
            Input(
                f"{hf_granite_blob}/main/granite-3b-code-base.Q4_K_M.gguf",
                "",
                "",
            ),
            "huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf",
        ),
        (
            Input(
                f"{hf_granite_blob}/main/granite-3b-code-base.Q4_K_M.gguf",
                "",
                "",
            ),
            "huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf",
        ),
        (
            Input("file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf", "", ""),
            "/tmp/models/granite-3b-code-base.Q4_K_M.gguf",
        ),
        (Input("granite-code", "huggingface", ""), "granite-code"),
        (Input("granite-code", "ollama", ""), "granite-code"),
        (Input("granite-code", "oci", ""), "granite-code"),
    ],
)
def test_prune_model_input(input: Input, expected: str):
    args = ARGS(input.Engine)
    pruned_model_input = ModelFactory(input.Model, args, input.Transport).prune_model_input()
    assert pruned_model_input == expected
