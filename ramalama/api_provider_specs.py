from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ramalama.config import CONFIG


@dataclass(frozen=True)
class APIProviderSpec:
    """Connection details for a hosted chat provider."""

    scheme: str
    base_url: str


DEFAULT_API_PROVIDER_SPECS: dict[str, APIProviderSpec] = {
    "openai": APIProviderSpec("openai", "https://api.openai.com/v1"),
}


PROVIDER_API_KEY_RESOLVERS: dict[str, Callable[[], str | None]] = {
    "openai": lambda: CONFIG.provider.openai_api_key,
}


def resolve_provider_api_key(scheme: str) -> str | None:
    """Return a configured API key for the given provider scheme, if any."""

    if resolver := PROVIDER_API_KEY_RESOLVERS.get(scheme):
        return resolver()
    return CONFIG.api_key


__all__ = [
    "APIProviderSpec",
    "DEFAULT_API_PROVIDER_SPECS",
    "PROVIDER_API_KEY_RESOLVERS",
    "resolve_provider_api_key",
]
