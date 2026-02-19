import warnings
from dataclasses import dataclass
from typing import Union
from unittest.mock import patch

import pytest

import ramalama.transports.transport_factory as transport_factory_module
from ramalama.chat_providers.openai import OpenAIResponsesChatProvider
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
    def test_new_warns_on_implicit_default_unprefixed_model(self, reset_warning_state):
        """FutureWarning is emitted when New() falls back to implicit default transport."""
        with patch("ramalama.transports.transport_factory.get_config") as mock_cfg:
            mock_cfg.return_value.transport = "ollama"
            mock_cfg.return_value.is_set.return_value = False
            with pytest.warns(FutureWarning, match="Defaulting to 'ollama' transport is deprecated"):
                transport = New("granite-code", ARGS(), transport=None)
        assert isinstance(transport, Ollama)
        assert mock_cfg.call_count == 1

    def test_new_no_warning_with_explicit_transport(self, reset_warning_state):
        """No FutureWarning when New() receives an explicit transport argument."""
        with patch("ramalama.transports.transport_factory.get_config") as mock_cfg:
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                transport = New("granite-code", ARGS(), transport="ollama")
        assert isinstance(transport, Ollama)
        assert not [w for w in captured if issubclass(w.category, FutureWarning)]
        mock_cfg.assert_not_called()

    def test_new_no_warning_with_prefixed_model(self, reset_warning_state):
        """No FutureWarning when New() is called with explicit model transport prefix."""
        with patch("ramalama.transports.transport_factory.get_config") as mock_cfg:
            mock_cfg.return_value.transport = "ollama"
            mock_cfg.return_value.is_set.return_value = False
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                transport = New("hf://org/model", ARGS(), transport=None)
        assert isinstance(transport, Huggingface)
        assert not [w for w in captured if issubclass(w.category, FutureWarning)]

    def test_warning_emitted_on_implicit_default(self, reset_warning_state):
        """FutureWarning fires when transport is not set in config/env and model has no prefix."""
        with patch("ramalama.transports.transport_factory.get_config") as mock_cfg:
            mock_cfg.return_value.is_set.return_value = False
            with pytest.warns(FutureWarning, match="Defaulting to 'ollama' transport is deprecated"):
                _warn_implicit_default_transport("granite-code")

    def test_no_warning_when_transport_set_in_config(self, reset_warning_state):
        """No warning when user explicitly set transport in config or env."""
        with patch("ramalama.transports.transport_factory.get_config") as mock_cfg:
            mock_cfg.return_value.is_set.return_value = True
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                _warn_implicit_default_transport("granite-code")
        assert not captured

    def test_no_warning_when_model_has_prefix(self, reset_warning_state):
        """No warning when model uses an explicit transport prefix."""
        with patch("ramalama.transports.transport_factory.get_config") as mock_cfg:
            mock_cfg.return_value.is_set.return_value = False
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                _warn_implicit_default_transport("ollama://granite-code")
        assert not captured

    def test_no_warning_when_hf_prefix_used(self, reset_warning_state):
        """No warning when model uses hf:// prefix."""
        with patch("ramalama.transports.transport_factory.get_config") as mock_cfg:
            mock_cfg.return_value.is_set.return_value = False
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                _warn_implicit_default_transport("hf://org/model")
        assert not captured

    def test_no_warning_when_default_transport_is_not_ollama(self, reset_warning_state):
        """No warning when DEFAULT_TRANSPORT no longer points to ollama."""
        with patch("ramalama.transports.transport_factory.DEFAULT_TRANSPORT", "huggingface"):
            with patch("ramalama.transports.transport_factory.get_config") as mock_cfg:
                mock_cfg.return_value.is_set.return_value = False
                with warnings.catch_warnings(record=True) as captured:
                    warnings.simplefilter("always")
                    _warn_implicit_default_transport("granite-code")
        assert not captured

    def test_warning_emitted_only_once(self, reset_warning_state):
        """FutureWarning fires at most once per process."""
        with patch("ramalama.transports.transport_factory.get_config") as mock_cfg:
            mock_cfg.return_value.is_set.return_value = False
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                _warn_implicit_default_transport("granite-code")
                _warn_implicit_default_transport("another-model")
        deprecation_warnings = [w for w in captured if issubclass(w.category, FutureWarning)]
        assert len(deprecation_warnings) == 1
        assert "Defaulting to 'ollama' transport is deprecated" in str(deprecation_warnings[0].message)


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
