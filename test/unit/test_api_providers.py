import pytest

from ramalama.chat_providers.api_providers import get_chat_provider
from ramalama.chat_providers.openai import OpenAIResponsesChatProvider
from ramalama.chat_providers.orcarouter import (
    ORCAROUTER_DEFAULT_BASE_URL,
    ORCAROUTER_DEFAULT_MODEL,
    OrcaRouterChatProvider,
)


def test_get_chat_provider_returns_openai_provider():
    provider = get_chat_provider("openai")

    assert isinstance(provider, OpenAIResponsesChatProvider)
    assert provider.base_url == "https://api.openai.com/v1"
    assert provider.provider == "openai"


def test_get_chat_provider_returns_orcarouter_provider():
    provider = get_chat_provider("orcarouter")

    assert isinstance(provider, OrcaRouterChatProvider)
    assert provider.base_url == ORCAROUTER_DEFAULT_BASE_URL
    assert provider.provider == "orcarouter"


def test_orcarouter_provider_default_model():
    assert ORCAROUTER_DEFAULT_MODEL == "orcarouter/auto"


def test_get_chat_provider_raises_for_unknown_scheme():
    with pytest.raises(ValueError):
        get_chat_provider("anthropic")
