from dataclasses import dataclass
from typing import Union
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

import ramalama.transports.transport_factory as transport_factory_module
from ramalama.chat_providers.openai import OpenAIResponsesChatProvider
from ramalama.transports.api import APITransport
from ramalama.transports.huggingface import Huggingface
from ramalama.transports.modelscope import ModelScope
from ramalama.transports.oci.oci import OCI
from ramalama.transports.ollama import Ollama
from ramalama.transports.rlcr import RamalamaContainerRegistry
from ramalama.transports.transport_factory import TransportFactory
from ramalama.transports.url import URL


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
        (Input("openai://gpt-4o-mini", "", ""), APITransport, None),
        (Input("huggingface://granite-code", "", ""), Huggingface, None),
        (Input("hf://granite-code", "", ""), Huggingface, None),
        (Input("hf.co/granite-code", "", ""), Huggingface, None),
        (Input("modelscope://granite-code", "", ""), ModelScope, None),
        (Input("ms://granite-code", "", ""), ModelScope, None),
        (Input("ollama://granite-code", "", ""), Ollama, None),
        (Input("ollama.com/library/granite-code", "", ""), Ollama, None),
        (Input("oci://granite-code", "", "podman"), OCI, None),
        (Input("docker://granite-code", "", "podman"), OCI, None),
        (Input("rlcr://granite-code", "", "podman"), RamalamaContainerRegistry, None),
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
            TransportFactory(input.Model, args, input.Transport).create()
    else:
        model = TransportFactory(input.Model, args, input.Transport).create()
        assert isinstance(model, expected)


@pytest.mark.parametrize(
    "input,error",
    [
        (Input("", "", ""), KeyError),
        (Input("oci://granite-code", "", "podman"), None),
        (Input("docker://granite-code", "", "podman"), None),
        (Input("rlcr://granite-code", "", "podman"), None),
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
            TransportFactory(input.Model, args, input.Transport).validate_oci_model_input()
        return

    TransportFactory(input.Model, args, input.Transport).validate_oci_model_input()


@pytest.mark.parametrize(
    "input,expected",
    [
        (Input("openai://gpt-4o-mini", "", ""), "gpt-4o-mini"),
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
        (Input("rlcr://granite-code", "", "podman"), "granite-code"),
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
    pruned_model_input = TransportFactory(input.Model, args, input.Transport).prune_model_input()
    assert pruned_model_input == expected


def test_transport_factory_passes_scheme_to_get_chat_provider(monkeypatch):
    args = ARGS()
    provider = OpenAIResponsesChatProvider("https://api.openai.com/v1")
    captured: dict[str, str] = {}

    def fake_get_chat_provider(scheme: str):
        captured["scheme"] = scheme
        return provider

    monkeypatch.setattr(transport_factory_module, "get_chat_provider", fake_get_chat_provider)

    transport = TransportFactory("openai://gpt-4o-mini", args).create()

    assert captured["scheme"] == "openai"
    assert isinstance(transport, APITransport)
    assert transport.provider is provider


def test_hf_pull_surfaces_http_error_not_notimplementederror():
    """Regression test: HTTP errors (e.g. 404) from HF API must be surfaced to
    the user rather than being masked by the generic 'huggingface cli download
    not available' NotImplementedError raised by get_cli_download_args()."""
    from argparse import Namespace

    args = Namespace(quiet=True, verify=True)
    model = Huggingface("huggingface://Qwen/Qwen2.5-7B-Instruct-GGUF/model.gguf", "/tmp/store")

    http_error_key = "failed to pull https://huggingface.co/...: HTTP Error 404: Not Found"

    mock_store = MagicMock()
    mock_store.get_cached_files.return_value = ("tag", [], False)
    mock_store.base_path = "/tmp/store"

    with patch.object(type(model), "model_store", new_callable=PropertyMock, return_value=mock_store):
        with patch.object(model, "create_repository", side_effect=KeyError(http_error_key)):
            with patch("ramalama.hf_style_repo_base.available", return_value=True):
                with patch("os.makedirs"), patch("tempfile.TemporaryDirectory") as mock_tmpdir:
                    mock_tmpdir.return_value.__enter__ = lambda s: "/tmp/fake"
                    mock_tmpdir.return_value.__exit__ = lambda s, *a: False
                    with pytest.raises(KeyError) as exc_info:
                        model.pull(args)

    assert http_error_key in str(exc_info.value)
