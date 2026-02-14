import logging
from dataclasses import dataclass
from typing import Union
from unittest.mock import patch

import pytest

import ramalama.transports.transport_factory as transport_factory_module
from ramalama.chat_providers.openai import OpenAIResponsesChatProvider
from ramalama.config import DEFAULT_TRANSPORT
from ramalama.transports.api import APITransport
from ramalama.transports.huggingface import Huggingface
from ramalama.transports.modelscope import ModelScope
from ramalama.transports.oci import OCI
from ramalama.transports.ollama import Ollama
from ramalama.transports.rlcr import RamalamaContainerRegistry
from ramalama.transports.transport_factory import (
    New,
    TransportFactory,
    _has_explicit_transport_prefix,
    _warn_implicit_default_transport,
)
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


@pytest.fixture(autouse=False)
def reset_warning_state():
    """Reset the once-per-process warning guard between tests."""
    transport_factory_module._default_transport_warned = False
    yield
    transport_factory_module._default_transport_warned = False


class TestHasExplicitTransportPrefix:
    @pytest.mark.parametrize(
        "model",
        [
            "huggingface://org/model",
            "hf://org/model",
            "hf.co/org/model",
            "ollama://granite-code",
            "ollama.com/library/granite-code",
            "oci://granite-code",
            "docker://granite-code",
            "rlcr://granite-code",
            "modelscope://org/model",
            "ms://org/model",
            "http://example.com/model.gguf",
            "https://example.com/model.gguf",
            "file:///tmp/model.gguf",
            "openai://gpt-4o-mini",
        ],
    )
    def test_returns_true_for_prefixed_models(self, model):
        assert _has_explicit_transport_prefix(model) is True

    @pytest.mark.parametrize(
        "model",
        [
            "granite-code",
            "ibm-granite/granite-3b-code-base-2k-GGUF",
            "",
        ],
    )
    def test_returns_false_for_unprefixed_models(self, model):
        assert _has_explicit_transport_prefix(model) is False


class TestWarnImplicitDefaultTransport:
    def test_warning_emitted_on_implicit_default(self, caplog, reset_warning_state):
        """Warning fires when transport is not set in config/env and model has no prefix."""
        with patch("ramalama.transports.transport_factory.get_config") as mock_cfg:
            mock_cfg.return_value.is_set.return_value = False
            mock_cfg.return_value.transport = DEFAULT_TRANSPORT
            with caplog.at_level(logging.WARNING, logger="ramalama"):
                _warn_implicit_default_transport("granite-code")
        assert "currently defaults to" in caplog.text
        assert DEFAULT_TRANSPORT in caplog.text

    def test_no_warning_when_transport_set_in_config(self, caplog, reset_warning_state):
        """No warning when user explicitly set transport in config or env."""
        with patch("ramalama.transports.transport_factory.get_config") as mock_cfg:
            mock_cfg.return_value.is_set.return_value = True
            with caplog.at_level(logging.WARNING, logger="ramalama"):
                _warn_implicit_default_transport("granite-code")
        assert caplog.text == ""

    def test_no_warning_when_model_has_prefix(self, caplog, reset_warning_state):
        """No warning when model uses an explicit transport prefix."""
        with patch("ramalama.transports.transport_factory.get_config") as mock_cfg:
            mock_cfg.return_value.is_set.return_value = False
            with caplog.at_level(logging.WARNING, logger="ramalama"):
                _warn_implicit_default_transport("ollama://granite-code")
        assert caplog.text == ""

    def test_no_warning_when_hf_prefix_used(self, caplog, reset_warning_state):
        """No warning when model uses hf:// prefix."""
        with patch("ramalama.transports.transport_factory.get_config") as mock_cfg:
            mock_cfg.return_value.is_set.return_value = False
            with caplog.at_level(logging.WARNING, logger="ramalama"):
                _warn_implicit_default_transport("hf://org/model")
        assert caplog.text == ""

    def test_warning_emitted_only_once(self, caplog, reset_warning_state):
        """Warning fires at most once per process."""
        with patch("ramalama.transports.transport_factory.get_config") as mock_cfg:
            mock_cfg.return_value.is_set.return_value = False
            mock_cfg.return_value.transport = DEFAULT_TRANSPORT
            with caplog.at_level(logging.WARNING, logger="ramalama"):
                _warn_implicit_default_transport("granite-code")
                _warn_implicit_default_transport("another-model")
        assert caplog.text.count("currently defaults to") == 1


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
