from collections.abc import Callable

from ramalama.chat_providers.anthropic import AnthropicChatProvider
from ramalama.chat_providers.base import ChatProvider
from ramalama.chat_providers.openai import OpenAIResponsesChatProvider
from ramalama.chat_providers.ramalama_labs import RamalamaLabsChatProvider
from ramalama.config import get_config


PROVIDER_API_KEY_RESOLVERS: dict[str, Callable[[], str | None]] = {
    "openai": lambda: get_config().provider.openai.api_key,
    "anthropic": lambda: get_config().provider.anthropic.api_key,
    "ramalamalabs": lambda: get_config().provider.ramalamalabs.api_key,
}


def get_provider_api_key(scheme: str) -> str | None:
    """Return a configured API key for the given provider scheme, if any."""

    if resolver := PROVIDER_API_KEY_RESOLVERS.get(scheme):
        return resolver()

    return get_config().api_key


DEFAULT_PROVIDERS = {
    "openai": lambda: OpenAIResponsesChatProvider(
        base_url="https://api.openai.com/v1", api_key=get_provider_api_key("openai")
    ),
    "anthropic": lambda: AnthropicChatProvider(
        base_url="https://api.anthropic.com", api_key=get_provider_api_key("anthropic")
    ),
    "ramalamalabs": lambda: RamalamaLabsChatProvider(
        base_url="https://gateway.ramalama.com", api_key=get_provider_api_key("ramalamalabs")
    ),
    "rl": lambda: RamalamaLabsChatProvider(
        base_url="https://gateway.ramalama.com", api_key=get_provider_api_key("ramalamalabs")
    ),
}


def get_chat_provider(scheme: str) -> ChatProvider:
    if (resolver := DEFAULT_PROVIDERS.get(scheme, None)) is None:
        raise ValueError(f"No support chat providers for {scheme}")
    return resolver()


__all__ = ["get_chat_provider", "get_provider_api_key"]
