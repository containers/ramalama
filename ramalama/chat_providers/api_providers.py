from collections.abc import Callable

from ramalama.chat_providers.base import ChatProvider
from ramalama.chat_providers.openai import OpenAIResponsesChatProvider
from ramalama.config import get_config

PROVIDER_API_KEY_RESOLVERS: dict[str, Callable[[], str | None]] = {
    "openai": lambda: get_config().provider.openai.api_key,
}


def get_provider_api_key(scheme: str) -> str | None:
    """Return a configured API key for the given provider scheme, if any."""

    if resolver := PROVIDER_API_KEY_RESOLVERS.get(scheme):
        return resolver()
    return get_config().api_key


DEFAULT_PROVIDERS = {
    "openai": lambda: OpenAIResponsesChatProvider(
        base_url="https://api.openai.com/v1", api_key=get_provider_api_key("openai")
    )
}


def get_chat_provider(scheme: str) -> ChatProvider:
    if (resolver := DEFAULT_PROVIDERS.get(scheme, None)) is None:
        raise ValueError(f"No support chat providers for {scheme}")
    return resolver()


__all__ = ["get_chat_provider", "get_provider_api_key"]
