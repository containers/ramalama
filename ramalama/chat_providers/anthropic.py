import base64
import json
from collections.abc import Iterable, Mapping, Sequence
from functools import singledispatch
from typing import Any, TypedDict
from urllib import error as urllib_error
from urllib import request as urllib_request

from ramalama.chat_providers.base import ChatProvider, ChatProviderError, ChatRequestOptions, ChatStreamEvent
from ramalama.chat_providers.errors import UnsupportedAnthropicMessageType
from ramalama.chat_utils import (
    AssistantMessage,
    ChatMessageType,
    ImageBytesPart,
    ImageURLPart,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from ramalama.config import get_config


def create_content_blocks(
    text: str | None,
    attachments: list[ImageURLPart | ImageBytesPart] | None = None,
) -> list[dict[str, Any]]:
    """Convert text and attachments to Anthropic content block format."""
    content: list[dict[str, Any]] = []

    for attachment in attachments or []:
        if isinstance(attachment, ImageURLPart):
            content.append(
                {
                    "type": "image",
                    "source": {"type": "url", "url": attachment.url},
                }
            )
        elif isinstance(attachment, ImageBytesPart):
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": attachment.mime_type,
                        "data": base64.b64encode(attachment.data).decode("ascii"),
                    },
                }
            )

    if text:
        content.append({"type": "text", "text": text})

    return content


@singledispatch
def message_to_anthropic_dict(message: Any) -> dict[str, Any]:
    msg = (
        f"Cannot convert message type `{type(message)}` to Anthropic format.\n"
        "Please create an issue at: https://github.com/containers/ramalama/issues"
    )
    raise UnsupportedAnthropicMessageType(msg)


@message_to_anthropic_dict.register
def _(message: UserMessage) -> dict[str, Any]:
    content = create_content_blocks(message.text, message.attachments)
    return {"role": "user", "content": content}


@message_to_anthropic_dict.register
def _(message: AssistantMessage) -> dict[str, Any]:
    content = create_content_blocks(message.text, message.attachments)

    for call in message.tool_calls:
        content.append(
            {
                "type": "tool_use",
                "id": call.id,
                "name": call.name,
                "input": call.arguments,
            }
        )

    return {"role": "assistant", "content": content}


@message_to_anthropic_dict.register
def _(message: ToolMessage) -> dict[str, Any]:
    content: list[dict[str, Any]] = [
        {
            "type": "tool_result",
            "tool_use_id": message.tool_call_id,
            "content": message.text,
        }
    ]
    return {"role": "user", "content": content}


class AnthropicPayload(TypedDict, total=False):
    model: str
    max_tokens: int
    messages: list[dict[str, Any]]
    system: str
    stream: bool
    temperature: float


class AnthropicChatProvider(ChatProvider):
    """Chat provider for Anthropic's Messages API."""

    provider = "anthropic"
    default_path = "/v1/messages"

    def __init__(self, base_url: str, api_key: str | None = None):
        super().__init__(base_url, api_key)
        self._stream_buffer: str = ""

        config = get_config()
        self.default_max_tokens = config.provider.anthropic.default_max_tokens
        self.anthropic_version = config.provider.anthropic.anthropic_version

    def auth_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"anthropic-version": self.anthropic_version}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def build_payload(self, messages: Sequence[ChatMessageType], options: ChatRequestOptions) -> AnthropicPayload:
        system_text: str | None = None
        api_messages: list[dict[str, Any]] = []

        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_text = msg.text
            else:
                api_messages.append(message_to_anthropic_dict(msg))

        api_messages = self._merge_consecutive_user_messages(api_messages)

        if options.model is None:
            raise ValueError("Anthropic requests require a model")

        payload: AnthropicPayload = {
            "model": options.model,
            "max_tokens": options.max_tokens or self.default_max_tokens,
            "messages": api_messages,
            "stream": options.stream,
        }

        if system_text:
            payload["system"] = system_text

        if options.temperature is not None:
            payload["temperature"] = options.temperature

        return payload

    @staticmethod
    def _merge_consecutive_user_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Merge consecutive user messages (e.g., user message followed by tool result)."""
        if not messages:
            return messages

        merged: list[dict[str, Any]] = []
        for msg in messages:
            if merged and merged[-1]["role"] == "user" and msg["role"] == "user":
                merged[-1]["content"].extend(msg["content"])
            else:
                merged.append(msg)

        return merged

    def parse_stream_chunk(self, chunk: bytes) -> Iterable[ChatStreamEvent]:
        events: list[ChatStreamEvent] = []
        self._stream_buffer += chunk.decode("utf-8")

        while "\n" in self._stream_buffer:
            line, self._stream_buffer = self._stream_buffer.split("\n", 1)
            line = line.strip()

            if not line:
                continue

            if line.startswith("event:"):
                continue

            if not line.startswith("data:"):
                continue

            payload_str = line[len("data:") :].strip()
            if not payload_str:
                continue

            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError:
                continue

            event = self._process_event(payload)
            if event:
                events.append(event)

        return events

    def _process_event(self, payload: Mapping[str, Any]) -> ChatStreamEvent | None:
        event_type = payload.get("type", "")

        if event_type == "content_block_delta":
            delta = payload.get("delta", {})
            if delta.get("type") == "text_delta":
                text = delta.get("text")
                if isinstance(text, str):
                    return ChatStreamEvent(text=text, raw=dict(payload))

        if event_type in ("message_stop", "message_delta"):
            stop_reason = payload.get("delta", {}).get("stop_reason")
            if event_type == "message_stop" or stop_reason:
                return ChatStreamEvent(done=True, raw=dict(payload))

        return None

    def list_models(self) -> list[str]:
        """Fetch available models from the Anthropic API."""

        req = urllib_request.Request(
            self.build_url("/v1/models"),
            headers=self.prepare_headers(include_auth=True),
            method="GET",
        )
        try:
            with urllib_request.urlopen(req) as response:
                payload = self.parse_response_body(response.read())
        except urllib_error.HTTPError as exc:
            raise ChatProviderError(f"Failed to list models: {exc.reason}", status_code=exc.code) from exc

        models: list[str] = []
        for entry in payload.get("data", []):
            if model_id := entry.get("id"):
                models.append(str(model_id))
        return models


__all__ = ["AnthropicChatProvider"]
