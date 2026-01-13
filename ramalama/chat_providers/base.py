import json
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from ramalama.chat_utils import ChatMessageType
from ramalama.config import get_config


@dataclass(slots=True)
class ChatRequestOptions:
    """Normalized knobs for building a chat completion request."""

    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = True
    extra: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        keys = ["model", "temperature", "max_tokens", "stream"]
        result = {k: v for k in keys if (v := getattr(self, k)) is not None}
        result |= {} if self.extra is None else dict(self.extra)
        return result


@dataclass(slots=True)
class ChatStreamEvent:
    """A provider-agnostic representation of a streamed delta."""

    text: str | None = None
    raw: dict[str, Any] | None = None
    done: bool = False


class ChatProviderError(Exception):
    """Raised when a provider request fails or returns an invalid payload."""

    def __init__(self, message: str, *, status_code: int | None = None, payload: Any | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class ChatProvider(ABC):
    """Abstract base class for hosted chat providers."""

    provider: str = "base"
    default_path: str

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        default_headers: Mapping[str, str] | None = None,
    ) -> None:
        if api_key is None:
            api_key = get_config().api_key

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._default_headers: dict[str, str] = dict(default_headers or {})

    def build_url(self, path: str | None = None) -> str:
        rel = path or self.default_path
        if not rel.startswith("/"):
            rel = f"/{rel}"
        return f"{self.base_url}{rel}"

    def prepare_headers(
        self,
        *,
        include_auth: bool = True,
        extra: dict[str, str] | None = None,
        options: ChatRequestOptions | None = None,
    ) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            **self._default_headers,
            **self.provider_headers(options),
        }

        if include_auth:
            headers.update(self.auth_headers())
        if extra:
            headers.update(extra)
        return headers

    def auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def serialize_payload(self, payload: Mapping[str, Any]) -> bytes:
        return json.dumps(payload).encode("utf-8")

    def create_request(
        self, messages: Sequence[ChatMessageType], options: ChatRequestOptions
    ) -> urllib_request.Request:
        payload = self.build_payload(messages, options)
        headers = self.prepare_headers(options=options, extra=self.additional_request_headers(options))
        body = self.serialize_payload(payload)
        return urllib_request.Request(
            self.build_url(self.resolve_request_path(options)),
            data=body,
            headers=headers,
            method="POST",
        )

    # ------------------------------------------------------------------
    # Provider customization points
    # ------------------------------------------------------------------
    def provider_headers(self, options: ChatRequestOptions | None = None) -> dict[str, str]:
        return {}

    def additional_request_headers(self, options: ChatRequestOptions | None = None) -> dict[str, str]:
        return {}

    def resolve_request_path(self, options: ChatRequestOptions | None = None) -> str:
        return self.default_path

    @abstractmethod
    def build_payload(self, messages: Sequence[ChatMessageType], options: ChatRequestOptions) -> Mapping[str, Any]:
        """Return the provider-specific payload."""

    @abstractmethod
    def parse_stream_chunk(self, chunk: bytes) -> Iterable[ChatStreamEvent]:
        """Yield zero or more events parsed from a streamed response chunk."""

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------
    def raise_for_status(self, status_code: int, payload: Any | None = None) -> None:
        if status_code >= 400:
            if isinstance(payload, dict) and "error" in payload:
                err = payload["error"]
                message = str(err.get("message") or err.get("type") or err) if isinstance(err, dict) else str(err)
            else:
                message = "chat request failed"

            raise ChatProviderError(message, status_code=status_code, payload=payload)

    # ------------------------------------------------------------------
    # Non-streamed helpers
    # ------------------------------------------------------------------
    def parse_response_body(self, body: bytes) -> Any:
        if not body:
            return None
        return json.loads(body.decode("utf-8"))

    def list_models(self) -> list[str]:
        """Return available model identifiers exposed by the provider."""

        request = urllib_request.Request(
            self.build_url("/models"),
            headers=self.prepare_headers(include_auth=True),
            method="GET",
        )
        try:
            with urllib_request.urlopen(request) as response:
                payload = self.parse_response_body(response.read())
        except urllib_error.HTTPError as exc:
            if exc.code in (401, 403):
                message = (
                    f"Could not authenticate with {self.provider}."
                    "The provided API key was either missing or invalid.\n"
                    f"Set RAMALAMA_API_KEY or ramalama.provider.<provider_name>.api_key."
                )
                try:
                    payload = self.parse_response_body(exc.read())
                except Exception:
                    payload = {}

                if details := payload.get("error", {}).get("message", None):
                    message = f"{message}\n\n{details}"

                raise ChatProviderError(message, status_code=exc.code) from exc
            raise

        if not isinstance(payload, Mapping):
            raise ChatProviderError("Invalid model list payload", payload=payload)

        data = payload.get("data")
        if not isinstance(data, list):
            raise ChatProviderError("Invalid model list payload", payload=payload)

        models: list[str] = []
        for entry in data:
            if isinstance(entry, Mapping) and (model_id := entry.get("id")):
                models.append(str(model_id))

        return models


__all__ = [
    "ChatProvider",
    "ChatProviderError",
    "ChatRequestOptions",
    "ChatStreamEvent",
]
