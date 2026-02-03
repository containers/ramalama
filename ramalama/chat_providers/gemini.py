import base64
import json
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, TypedDict, cast
from urllib import error as urllib_error
from urllib import request as urllib_request

from ramalama.chat_providers.base import APIKeyChatProvider, ChatProviderError, ChatRequestOptions, ChatStreamEvent
from ramalama.chat_utils import (
    AssistantMessage,
    AttachmentPart,
    ChatMessageType,
    ImageBytesPart,
    ImageURLPart,
    SystemMessage,
    ToolMessage,
    UserMessage,
)


class GeminiGenerateContentPayload(TypedDict, total=False):
    contents: list[dict[str, Any]]
    system_instruction: dict[str, Any]
    generation_config: dict[str, Any]


def _ensure_base64_data(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _parse_data_url(url: str) -> dict[str, str]:
    if not url.startswith("data:"):
        raise ValueError("Gemini provider only supports data: URLs for image inputs.")

    header, _, data = url.partition(",")
    if not data:
        raise ValueError("Invalid data URL: missing payload.")

    header = header[len("data:") :]
    parts = header.split(";")
    mime_type = parts[0] or "application/octet-stream"
    if "base64" not in parts[1:]:
        raise ValueError("Invalid data URL: only base64-encoded images are supported.")

    return {"mime_type": mime_type, "data": data}


def _attachment_to_part(attachment: AttachmentPart) -> dict[str, Any]:
    if isinstance(attachment, ImageBytesPart):
        return {
            "inline_data": {
                "mime_type": attachment.mime_type or "application/octet-stream",
                "data": _ensure_base64_data(attachment.data),
            }
        }
    if isinstance(attachment, ImageURLPart):
        return {"inline_data": _parse_data_url(attachment.url)}

    raise TypeError(f"Unsupported attachment type: {type(attachment)!r}")


def _message_parts(text: str | None, attachments: list[AttachmentPart]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    if text:
        parts.append({"text": text})
    for attachment in attachments:
        parts.append(_attachment_to_part(attachment))
    return parts


class GeminiChatProvider(APIKeyChatProvider):
    provider = "gemini"
    default_path: str = "/v1beta/models"

    def __init__(self, base_url: str, api_key: str | None = None):
        super().__init__(base_url, api_key)
        self._stream_buffer: str = ""

    def auth_headers(self) -> dict[str, str]:
        return {"x-goog-api-key": self.api_key} if self.api_key else {}

    def resolve_request_path(self, options: ChatRequestOptions | None = None) -> str:
        if options is None or not options.model:
            raise ValueError("Gemini requests require a model value.")

        model_name = options.model
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"

        action = "streamGenerateContent" if options.stream else "generateContent"
        path = f"/v1beta/{model_name}:{action}"
        if options.stream:
            path = f"{path}?alt=sse"
        return path

    def build_payload(
        self, messages: Sequence[ChatMessageType], options: ChatRequestOptions
    ) -> GeminiGenerateContentPayload:
        if options.model is None:
            raise ValueError("Gemini requests require a model value.")

        contents: list[dict[str, Any]] = []
        system_messages: list[str] = []

        for message in messages:
            if isinstance(message, SystemMessage):
                if message.text:
                    system_messages.append(message.text)
                continue

            if isinstance(message, ToolMessage):
                raise ValueError("Tool messages are not supported by the Gemini provider yet.")

            if isinstance(message, AssistantMessage) and message.tool_calls:
                raise ValueError("Tool calls are not supported by the Gemini provider yet.")

            if isinstance(message, UserMessage):
                role = "user"
                parts = _message_parts(message.text, message.attachments)
            elif isinstance(message, AssistantMessage):
                role = "model"
                parts = _message_parts(message.text, message.attachments)
            else:
                raise TypeError(f"Unsupported message type: {type(message)!r}")

            contents.append({"role": role, "parts": parts})

        payload: GeminiGenerateContentPayload = {"contents": contents}

        if system_messages:
            payload["system_instruction"] = {"parts": [{"text": "\n\n".join(system_messages)}]}

        generation_config: dict[str, Any] = {}
        if options.temperature is not None:
            generation_config["temperature"] = options.temperature
        if options.max_tokens is not None and options.max_tokens > 0:
            generation_config["max_output_tokens"] = options.max_tokens
        if generation_config:
            payload["generation_config"] = generation_config

        payload_data: dict[str, Any] = dict(payload)
        if options.extra:
            payload_data.update(options.extra)

        return cast(GeminiGenerateContentPayload, payload_data)

    def parse_stream_chunk(self, chunk: bytes) -> Iterable[ChatStreamEvent]:
        events: list[ChatStreamEvent] = []
        self._stream_buffer += chunk.decode("utf-8")
        if "\r\n" in self._stream_buffer:
            self._stream_buffer = self._stream_buffer.replace("\r\n", "\n")

        while "\n\n" in self._stream_buffer:
            raw_event, self._stream_buffer = self._stream_buffer.split("\n\n", 1)
            raw_event = raw_event.strip()
            if not raw_event:
                continue

            data_lines: list[str] = []
            for line in raw_event.splitlines():
                if line.startswith("data:"):
                    data_lines.append(line[len("data:") :].strip())

            data = "\n".join(data_lines).strip()
            if not data:
                continue

            if data == "[DONE]":
                events.append(ChatStreamEvent(done=True))
                continue

            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                continue

            if text := self._extract_text(payload):
                events.append(ChatStreamEvent(text=text, raw=payload))
            elif self._is_done(payload):
                events.append(ChatStreamEvent(done=True, raw=payload))

        return events

    @staticmethod
    def _extract_text(payload: Mapping[str, Any]) -> str | None:
        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return None

        first = candidates[0]
        if not isinstance(first, Mapping):
            return None

        content = first.get("content")
        if not isinstance(content, Mapping):
            return None

        parts = content.get("parts")
        if not isinstance(parts, list) or not parts:
            return None

        text_parts: list[str] = []
        for part in parts:
            if isinstance(part, Mapping):
                text = part.get("text")
                if isinstance(text, str):
                    text_parts.append(text)

        if text_parts:
            return "".join(text_parts)
        return None

    @staticmethod
    def _is_done(payload: Mapping[str, Any]) -> bool:
        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return False

        first = candidates[0]
        if not isinstance(first, Mapping):
            return False

        finish_reason = first.get("finishReason")
        return bool(finish_reason)

    def list_models(self) -> list[str]:
        request = urllib_request.Request(
            self.build_url("/v1beta/models"),
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
                    f"Set RAMALAMA_API_KEY or ramalama.provider.{self.provider}.api_key."
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

        raw_models = payload.get("models")
        if not isinstance(raw_models, list):
            raise ChatProviderError("Invalid model list payload", payload=payload)

        models: list[str] = []
        for entry in raw_models:
            if not isinstance(entry, Mapping):
                continue
            name = entry.get("name")
            if isinstance(name, str):
                models.append(name.removeprefix("models/"))

        return models


__all__ = ["GeminiChatProvider"]
