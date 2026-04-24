from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from ramalama.chat_providers.base import ChatProvider
from ramalama.chat_providers.openai import OpenAIResponsesChatProvider
from ramalama.config import ActiveConfig

PROVIDER_API_KEY_RESOLVERS: dict[str, Callable[[], Optional[str]]] = {
    "openai": lambda: ActiveConfig().provider.openai.api_key,
}


def get_provider_api_key(scheme: str) -> Optional[str]:
    """Return a configured API key for the given provider scheme, if any."""

    if resolver := PROVIDER_API_KEY_RESOLVERS.get(scheme):
        if key := resolver():
            return key
    return ActiveConfig().api_key


DEFAULT_PROVIDERS = {
    "openai": lambda: OpenAIResponsesChatProvider(
        base_url="https://api.openai.com/v1", api_key=get_provider_api_key("openai")
    )
}


def get_chat_provider(scheme: str) -> ChatProvider:
    if (resolver := DEFAULT_PROVIDERS.get(scheme, None)) is None:
        raise ValueError(f"No supported chat provider for {scheme}")
    return resolver()


__all__ = ["get_chat_provider", "get_provider_api_key"]
