import types

import pytest

from ramalama import chat as chat_module
from ramalama.chat_providers.openai import OpenAIHostedChatProvider


def make_args(**overrides):
    defaults = {
        "model": None,
        "url": "http://127.0.0.1:8080/v1",
        "api_key": None,
        "runtime": "llama.cpp",
        "prefix": "> ",
        "color": "auto",
        "rag": None,
        "keepalive": None,
        "name": None,
        "pid2kill": None,
        "summarize_after": 0,
        "mcp": None,
        "ARGS": None,
    }
    defaults.update(overrides)
    return types.SimpleNamespace(**defaults)


def test_resolve_hosted_provider_returns_none_without_scheme():
    args = make_args(model="smollm")

    assert chat_module._resolve_hosted_provider(args) is None
    assert args.model == "smollm"


def test_resolve_hosted_provider_configures_openai(monkeypatch):
    args = make_args(model="openai://gpt-4o-mini")
    monkeypatch.setattr(chat_module.CONFIG.provider, "openai_api_key", "cfg-key")

    provider = chat_module._resolve_hosted_provider(args)

    assert isinstance(provider, OpenAIHostedChatProvider)
    assert args.model == "gpt-4o-mini"
    assert args.url == "https://api.openai.com/v1"
    assert args.api_key == "cfg-key"


def test_resolve_hosted_provider_with_unknown_scheme():
    args = make_args(model="unknown://model")

    with pytest.raises(ValueError):
        chat_module._resolve_hosted_provider(args)
