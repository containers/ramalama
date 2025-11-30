"""OpenAI-compatible chat provider implementation."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from ramalama.chat_providers.base import ChatProvider, ChatRequestOptions, ChatStreamEvent
from ramalama.chat_utils import AttachmentPart, ChatMessage, ToolCall, serialize_part


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

                if delta := self._extract_delta(parsed):
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
        if not isinstance(delta, Mapping):
            return None

        content = delta.get("content")
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: list[str] = []
            for entry in content:
                if not isinstance(entry, Mapping):
                    continue
                entry_type = entry.get("type")
                text_value = entry.get("text")
                if entry_type in {"text", "output_text"} and isinstance(text_value, str):
                    parts.append(text_value)
            if parts:
                return "".join(parts)

        return None

    def _serialize_message(self, message: ChatMessage) -> dict[str, Any]:
        if message.attachments:
            raise ValueError("Attachments are not supported by this provider.")
        payload: dict[str, Any] = {"role": message.role}
        if message.tool_calls:
            payload["tool_calls"] = [self._serialize_tool_call(call) for call in message.tool_calls]
        if message.tool_call_id:
            payload["tool_call_id"] = message.tool_call_id
        payload["content"] = message.text or ""
        payload |= message.metadata
        return payload

    def _serialize_tool_call(self, call: ToolCall) -> dict[str, Any]:
        return {
            "id": call.id,
            "type": "function",
            "function": {
                "name": call.name,
                "arguments": json.dumps(call.arguments, ensure_ascii=False),
            },
        }


class OpenAIHostedChatProvider(OpenAIChatProvider):
    def build_payload(self, messages: Sequence[ChatMessage], options: ChatRequestOptions) -> dict[str, object]:
        payload = super().build_payload(messages, options)
        max_tokens = payload.pop("max_tokens", None)

        if max_tokens is not None and (max_tokens := int(max_tokens)) > 0:
            payload.setdefault("max_completion_tokens", max_tokens)

        # OpenAI doesn't accept max_completion_tokens of 0 as unlimited
        if payload.get("max_completion_tokens") == 0:
            payload.pop("max_completion_tokens")

        return payload

    def _serialize_message(self, message: ChatMessage) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": message.role}
        if message.tool_calls:
            payload["tool_calls"] = [self._serialize_tool_call(call) for call in message.tool_calls]
        if message.tool_call_id:
            payload["tool_call_id"] = message.tool_call_id
        payload["content"] = self._structured_content(message.text, message.attachments)
        payload |= message.metadata
        return payload

    def _structured_content(self, text: str | None, attachments: list[AttachmentPart]) -> list[dict[str, Any]] | str:
        parts: list[dict[str, Any]] = []
        if text:
            parts.append({"type": "text", "text": text})
        for attachment in attachments:
            parts.append(serialize_part(attachment))
        return parts or ""


__all__ = ["OpenAIChatProvider", "OpenAIHostedChatProvider"]
