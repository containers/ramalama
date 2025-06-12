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
    UseModelStore: bool
    Transport: str
    Engine: str


class ARGS:
    store = "/tmp/store"
    use_model_store = True
    engine = ""
    container = True

    def __init__(self, store=False, engine=""):
        self.use_model_store = store
        self.engine = engine


hf_granite_blob = "https://huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob"


@pytest.mark.parametrize(
    "input,expected,error",
    [
        (Input("", False, "", ""), None, KeyError),
        (Input("huggingface://granite-code", False, "", ""), Huggingface, None),
        (Input("hf://granite-code", False, "", ""), Huggingface, None),
        (Input("hf.co/granite-code", False, "", ""), Huggingface, None),
        (Input("modelscope://granite-code", False, "", ""), ModelScope, None),
        (Input("ms://granite-code", False, "", ""), ModelScope, None),
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
        (Input("granite-code", False, "oci", ""), OCI, ValueError),
    ],
)
def test_model_factory_create(input: Input, expected: type[Union[Huggingface, Ollama, URL, OCI]], error):
    args = ARGS(input.UseModelStore, input.Engine)

    if error is not None:
        with pytest.raises(error):
            ModelFactory(input.Model, args, input.Transport).create()
    else:
        model = ModelFactory(input.Model, args, input.Transport).create()
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
        (Input("modelscope://granite-code", False, "", ""), ValueError),
        (Input("ms://granite-code", False, "", ""), ValueError),
        (Input("ollama://granite-code", False, "", ""), ValueError),
        (Input("ollama.com/library/granite-code", False, "", ""), None),
        (Input("granite-code", False, "ollama", ""), None),
        (Input("granite-code", False, "", ""), KeyError),
    ],
)
def test_validate_oci_model_input(input: Input, error):
    args = ARGS(input.UseModelStore, input.Engine)

    if error is not None:
        with pytest.raises(error):
            ModelFactory(input.Model, args, input.Transport).validate_oci_model_input()
        return

    ModelFactory(input.Model, args, input.Transport).validate_oci_model_input()


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
        (Input("modelscope://granite-code", False, "", ""), "granite-code"),
        (
            Input("modelscope://ibm-granite/granite-3b-code-base-2k-GGUF/granite-code", False, "", ""),
            "ibm-granite/granite-3b-code-base-2k-GGUF/granite-code",
        ),
        (Input("ms://granite-code", False, "", ""), "granite-code"),
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
    args = ARGS(input.UseModelStore, input.Engine)
    pruned_model_input = ModelFactory(input.Model, args, input.Transport).prune_model_input()
    assert pruned_model_input == expected


@pytest.mark.parametrize(
    "model_input,expected_type",
    [
        ("file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf", "file"),
        (f"{hf_granite_blob}/main/granite-3b-code-base.Q4_K_M.gguf", "https"),
        (
            "http://huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf",
            "http",
        ),
        ("hf://granite-code", "huggingface"),
        ("ollama://granite-code", "ollama"),
        ("oci://granite-code", "oci"),
    ],
)
def test_set_optional_model_store(model_input: str, expected_type: str):
    model = ModelFactory(model_input, args=ARGS(True, "podman")).create()
    assert expected_type == model.model_type
    assert expected_type == model.store.model_type
