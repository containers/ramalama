import os
from types import SimpleNamespace

os.environ.setdefault("RAMALAMA_CONFIG", "/dev/null")

from ramalama.transports import api as api_module
from ramalama.transports.api import APITransport
from ramalama.api_provider_specs import APIProviderSpec


def test_api_transport_run(monkeypatch):
    provider = APIProviderSpec("openai", "https://api.openai.com/v1")
    transport = APITransport("gpt-4o-mini", provider)
    recorded: dict[str, object] = {}

    def fake_chat(args, operational_args=None, provider=None):
        recorded["args"] = args
        recorded["operational_args"] = operational_args
        recorded["provider"] = provider

    monkeypatch.setattr(api_module, "chat", fake_chat)

    args = SimpleNamespace(container=True, engine="podman", url="http://localhost", model=None, api="none")
    transport.run(args, [])

    assert args.container is False
    assert args.engine is None
    assert args.url == provider.base_url
    assert args.model == "gpt-4o-mini"
    assert args.api == provider.scheme
    assert recorded["args"] is args


def test_api_transport_ensure_exists_mutates_args():
    provider = APIProviderSpec("openai", "https://api.openai.com/v1")
    transport = APITransport("gpt-4", provider)
    args = SimpleNamespace(container=True, engine="podman")

    transport.ensure_model_exists(args)

    assert args.container is False
    assert args.engine is None


def test_api_transport_falls_back_to_config_api_key(monkeypatch):
    provider = APIProviderSpec("openai", "https://api.openai.com/v1")
    transport = APITransport("gpt-4o-mini", provider)
    monkeypatch.setattr(api_module.CONFIG.provider, "openai_api_key", "config-secret")
    monkeypatch.setattr(api_module.CONFIG, "api_key", None)

    recorded: dict[str, object] = {}

    def fake_chat(args, operational_args=None, provider=None):
        recorded["args"] = args

    monkeypatch.setattr(api_module, "chat", fake_chat)

    args = SimpleNamespace(
        container=True, engine="podman", url="http://localhost", model=None, api_key=None, api="none"
    )
    transport.run(args, [])

    assert args.api_key == "config-secret"
    assert recorded["args"] is args
