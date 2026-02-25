from types import SimpleNamespace
from unittest import mock

import pytest

from ramalama.chat_providers.openai import OpenAIResponsesChatProvider
from ramalama.config import get_config
from ramalama.transports import api as api_module
from ramalama.transports.api import APITransport

CONFIG = get_config()


def make_provider(api_key: str = "provider-default") -> OpenAIResponsesChatProvider:
    return OpenAIResponsesChatProvider("https://api.openai.com/v1", api_key=api_key)


def test_api_transport_run(monkeypatch):
    provider = make_provider()
    transport = APITransport("gpt-4o-mini", provider)
    recorded: dict[str, object] = {}

    def fake_chat(args, operational_args=None, provider=None):
        recorded["args"] = args
        recorded["operational_args"] = operational_args
        recorded["provider"] = provider

    monkeypatch.setattr(api_module, "chat", fake_chat)

    args = SimpleNamespace(
        container=True, engine="podman", url="http://localhost", model=None, api="none", api_key=None
    )
    transport.run(args, [])

    assert args.container is False
    assert args.engine is None
    assert args.url == provider.base_url
    assert args.model == "gpt-4o-mini"
    assert recorded["args"] is args
    assert recorded["provider"] is provider
    assert provider.base_url == "http://localhost"
    assert provider.api_key == "provider-default"


def test_api_transport_ensure_exists_mutates_args(monkeypatch):
    provider = make_provider()
    transport = APITransport("gpt-4", provider)
    args = SimpleNamespace(container=True, engine="podman")
    monkeypatch.setattr(provider, "list_models", lambda: ["gpt-4", "other"])

    transport.ensure_model_exists(args)

    assert args.container is False
    assert args.engine is None


def test_api_transport_ensure_exists_requires_api_key(monkeypatch):
    monkeypatch.setattr(CONFIG, "api_key", None)
    provider = make_provider(api_key=None)
    transport = APITransport("gpt-4", provider)
    args = SimpleNamespace(container=True, engine="podman")

    with pytest.raises(ValueError, match="Missing API key"):
        transport.ensure_model_exists(args)


def test_api_transport_overrides_provider_api_key(monkeypatch):
    provider = make_provider()
    transport = APITransport("gpt-4o-mini", provider)

    recorded: dict[str, object] = {}

    def fake_chat(args, operational_args=None, provider=None):
        recorded["provider"] = provider

    monkeypatch.setattr(api_module, "chat", fake_chat)

    args = SimpleNamespace(container=True, engine="podman", url=None, model=None, api="none", api_key="cli-secret")
    transport.run(args, [])

    assert provider.api_key == "cli-secret"
    assert recorded["provider"] is provider


def test_api_transport_ensure_exists_raises_if_model_missing(monkeypatch):
    provider = make_provider()
    transport = APITransport("gpt-4", provider)
    monkeypatch.setattr(provider, "list_models", lambda: ["gpt-3.5"])
    args = SimpleNamespace(container=True, engine="podman")

    with pytest.raises(ValueError):
        transport.ensure_model_exists(args)


def test_run_cli_api_transport_does_not_call_pull(monkeypatch):
    from ramalama import cli as cli_module

    provider = make_provider()
    transport = APITransport("gpt-4o-mini", provider)

    monkeypatch.setattr(provider, "list_models", lambda: ["gpt-4o-mini"])
    monkeypatch.setattr(cli_module, "compute_serving_port", lambda args: "8080")
    monkeypatch.setattr(cli_module, "assemble_command_lazy", lambda args: [])
    monkeypatch.setattr(cli_module, "New", lambda model, args: transport)

    transport.pull = mock.Mock()
    transport.run = mock.Mock()

    args = SimpleNamespace(
        MODEL="openai://gpt-4o-mini",
        rag=None,
        container=True,
        engine="podman",
        api="none",
        pull="always",
        dryrun=False,
        quiet=True,
        url=None,
        api_key=None,
    )

    cli_module.run_cli(args)

    transport.pull.assert_not_called()
    transport.run.assert_called_once()
