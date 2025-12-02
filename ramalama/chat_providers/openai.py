"""OpenAI-compatible chat provider implementation."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from ramalama.chat_utils import ChatMessage, serialize_part

from ramalama.chat_providers.base import ChatProvider, ChatRequestOptions, ChatStreamEvent


class OpenAIChatProvider(ChatProvider):
    provider = "openai"

    def __init__(self, base_url: str, api_key: str | None = None):
        super().__init__(base_url, api_key)
        self._stream_buffer: str = ""

    def build_payload(self, messages: Sequence[ChatMessage], options: ChatRequestOptions) -> dict[str, object]:
        payload: dict[str, object] = {
            "messages": [self._serialize_message(m) for m in messages],
            **options.to_dict(),
        }
        return payload

    def parse_stream_chunk(self, chunk: bytes) -> Iterable[ChatStreamEvent]:
        events: list[ChatStreamEvent] = []
        self._stream_buffer += chunk.decode("utf-8")

        while "\n\n" in self._stream_buffer:
            raw_event, self._stream_buffer = self._stream_buffer.split("\n\n", 1)
            raw_event = raw_event.strip()
            if not raw_event:
                continue
            for line in raw_event.splitlines():
                if not line.startswith("data:"):
                    continue
                payload = line[len("data:") :].strip()
                if not payload:
                    continue
                if payload == "[DONE]":
                    events.append(ChatStreamEvent(done=True))
                    continue
                try:
                    parsed = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                delta = self._extract_delta(parsed)
                if delta:
                    events.append(ChatStreamEvent(text=delta, raw=parsed))

        return events

    def _extract_delta(self, payload: Mapping[str, object]) -> str | None:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        choice = choices[0]
        if not isinstance(choice, Mapping):
            return None
        delta = choice.get("delta")
        if isinstance(delta, Mapping):
            content = delta.get("content")
            if isinstance(content, str):
                return content
        return None

    def _serialize_message(self, message: ChatMessage) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": message.role}
        if message.parts:
            payload["content"] = [serialize_part(part) for part in message.parts]
        else:
            payload["content"] = ""
        payload.update(message.metadata)
        return payload


class OpenAIHostedChatProvider(OpenAIChatProvider):
    def build_payload(self, messages: Sequence[ChatMessage], options: ChatRequestOptions) -> dict[str, object]:
        payload = super().build_payload(messages, options)
        max_tokens = payload.pop("max_tokens", None)
        if max_tokens is not None:
            payload["max_completion_tokens"] = max_tokens

        if payload["max_completion_tokens"] == 0:
            payload.pop("max_completion_tokens")

        return payload


__all__ = ["OpenAIChatProvider", "OpenAIHostedChatProvider"]
