from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ramalama.chat import chat
from ramalama.chat_providers.openai import OpenAIHostedChatProvider
from ramalama.config import CONFIG
from ramalama.transports.base import TransportBase


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


class APITransport(TransportBase):
    """Transport that proxies chat requests to a hosted API provider."""

    type: str = "api"

    def __init__(self, model: str, provider: APIProviderSpec, base_url: str | None = None):
        self.model = model
        self.provider = provider
        self.base_url = (base_url or provider.base_url).rstrip("/")

        self._model_name = model
        self._model_tag = "latest"
        self._model_organization = provider.scheme
        self.draft_model = None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_tag(self) -> str:
        return self._model_tag

    @property
    def model_organization(self) -> str:
        return self._model_organization

    def remove(self, args):
        raise NotImplementedError("Hosted API transports do not support removing remote models.")

    def bench(self, args, cmd: list[str]):
        raise NotImplementedError("bench is not supported for hosted API transports.")

    def run(self, args, server_cmd: list[str]):  # pragma: no cover - exercised via CLI integration
        """Connect directly to the provider instead of launching a local server."""
        args.container = False
        args.engine = None
        args.url = self.base_url
        if not getattr(args, "api_key", None):
            key = self._resolve_api_key()
            if key:
                args.api_key = key
        args.model = self.model_name
        args.api = self.provider.scheme
        provider = self._build_chat_provider(args)
        chat(args, provider=provider)
        return 0

    def perplexity(self, args, cmd: list[str]):
        raise NotImplementedError("perplexity is not supported for hosted API transports.")

    def serve(self, args, cmd: list[str]):
        raise NotImplementedError("Hosted API transports cannot be served locally.")

    def exists(self) -> bool:
        return True

    def inspect(self, args):
        return {
            "provider": self.provider.scheme,
            "model": self.model_name,
            "base_url": self.base_url,
        }

    def ensure_model_exists(self, args):
        args.container = False
        args.engine = None
        return

    def _resolve_api_key(self) -> str | None:
        resolver = PROVIDER_API_KEY_RESOLVERS.get(self.provider.scheme)
        if resolver:
            return resolver()
        return CONFIG.api_key

    def _build_chat_provider(self, args):
        if self.provider.scheme == "openai":
            return OpenAIHostedChatProvider(args.url, getattr(args, "api_key", None))
        return None
