from typing import Any

from ramalama.chat import chat
from ramalama.chat_providers.base import ChatProvider, ChatProviderError
from ramalama.common import perror
from ramalama.transports.base import TransportBase


class APITransport(TransportBase):
    """Transport that proxies chat requests to a hosted API provider."""

    type: str = "api"

    def __init__(self, model: str, provider: ChatProvider):
        self.model = model
        self.provider = provider

        self._model_tag = "latest"
        self._model_name = self.model
        self.draft_model = None

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def model_tag(self) -> str:
        return self._model_tag

    @property
    def model_organization(self) -> str:
        return self.provider.provider

    @property
    def model_type(self) -> str:
        return self.type

    @property
    def model_alias(self):
        return f"{self.model_organization}/{self.model_name}"

    def _get_entry_model_path(self, use_container: bool, should_generate: bool, dry_run: bool) -> str:
        return ''

    def _get_mmproj_path(self, use_container: bool, should_generate: bool, dry_run: bool):
        return None

    def _get_chat_template_path(self, use_container: bool, should_generate: bool, dry_run: bool):
        return None

    def remove(self, args):
        raise NotImplementedError("Hosted API transports do not support removing remote models.")

    def bench(self, args, cmd: list[str]):
        raise NotImplementedError("bench is not supported for hosted API transports.")

    def run(self, args, server_cmd: list[str]):
        """Connect directly to the provider instead of launching a local server."""
        args.container = False
        args.engine = None
        args.model = self.model

        if getattr(args, "url", None):
            self.provider.base_url = args.url

        if getattr(args, "api_key", None):
            self.provider.api_key = args.api_key

        chat(args, provider=self.provider)

    def perplexity(self, args, cmd: list[str]):
        raise NotImplementedError("perplexity is not supported for hosted API transports.")

    def serve(self, args, cmd: list[str]):
        raise NotImplementedError("Hosted API transports cannot be served locally.")

    def exists(self) -> bool:
        return True

    def inspect(self, args):
        return {
            "provider": self.provider.provider,
            "model": self.model_name,
            "base_url": self.provider.base_url,
        }

    def ensure_model_exists(self, args):
        args.container = False
        args.engine = None
        if not self.provider.api_key:
            raise ValueError(
                f'Missing API key for provider "{self.provider.provider}". '
                "Set RAMALAMA_API_KEY or ramalama.provider.openai.api_key."
            )
        try:
            models = self.provider.list_models()
        except ChatProviderError as exc:
            raise ValueError(str(exc)) from exc
        except Exception as exc:
            raise RuntimeError(f'Failed to list models for provider "{self.provider.provider}"') from exc

        if self.model not in models:
            available = ", ".join(models) if models else "none"
            raise ValueError(
                f'Model "{self.model}" not available from provider "{self.provider.provider}". '
                f"Available models: {available}"
            )

    def pull(self, args: Any):
        perror(f"{self.model} is provided over a hosted API preventing direct pulling of the model file.")
