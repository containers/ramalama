import json
from collections.abc import Iterable, Mapping, Sequence
from functools import singledispatch
from typing import Any, TypedDict

from ramalama.chat_providers.base import ChatProvider, ChatRequestOptions, ChatStreamEvent
from ramalama.chat_providers.errors import UnsupportedOpenaiMessageType
from ramalama.chat_utils import (
    AssistantMessage,
    AttachmentPart,
    ChatMessageType,
    SystemMessage,
    ToolMessage,
    UserMessage,
    serialize_part,
)


@singledispatch
def message_to_completions_dict(message: Any) -> dict[str, Any]:
    message = (
        f"Cannot convert message type `{type(message)}` to a completions dictionary.\n"
        "Please create an issue at: https://github.com/containers/ramalama/issues"
    )
    raise UnsupportedOpenaiMessageType(message)


@message_to_completions_dict.register
def _(message: SystemMessage) -> dict[str, Any]:
    return {**message.metadata, 'content': message.text or "", 'role': message.role}


@message_to_completions_dict.register
def _(message: ToolMessage) -> dict[str, Any]:
    response = {
        **message.metadata,
        'content': message.text or "",
        'role': message.role,
    }
    if message.tool_call_id:
        response['tool_call_id'] = message.tool_call_id

    return response


@message_to_completions_dict.register
def _(message: UserMessage) -> dict[str, Any]:
    if message.attachments:
        raise ValueError("Attachments are not supported by this provider.")
    return {**message.metadata, 'content': message.text or "", 'role': message.role}


@message_to_completions_dict.register
def _(message: AssistantMessage) -> dict[str, Any]:
    if message.attachments:
        raise ValueError("Attachments are not supported by this provider.")

    payload: dict[str, Any] = {
        **message.metadata,
        'content': message.text or "",
        'role': message.role,
    }
    tool_calls = [
        {
            "id": call.id,
            "type": "function",
            "function": {
                "name": call.name,
                "arguments": json.dumps(call.arguments, ensure_ascii=False),
            },
        }
        for call in message.tool_calls
    ]
    if tool_calls:
        payload['tool_calls'] = tool_calls
    return payload


class CompletionsPayload(TypedDict, total=False):
    messages: list[dict[str, Any]]
    model: str | None
    temperature: float | None
    max_tokens: int | None
    stream: bool


class OpenAICompletionsChatProvider(ChatProvider):
    provider = "openai"
    default_path = "/chat/completions"

    def __init__(self, base_url: str, api_key: str | None = None):
        super().__init__(base_url, api_key)
        self._stream_buffer: str = ""

    def build_payload(self, messages: Sequence[ChatMessageType], options: ChatRequestOptions) -> CompletionsPayload:
        payload: CompletionsPayload = {
            "messages": [message_to_completions_dict(m) for m in messages],
            "model": options.model,
            "temperature": options.temperature,
            "max_tokens": options.max_tokens,
            "stream": options.stream,
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


@singledispatch
def message_to_responses_dict(message: Any) -> dict[str, Any]:
    raise ValueError(f"Undefined message type {type(message)}")


def create_responses_content(
    text: str | None, attachments: list[AttachmentPart], content_type: str
) -> list[dict[str, Any]] | str:
    """
    TODO: Current structure doesn't correctly reflect document ordering
    (i.e. the possibility of messages interspersed with content)
    """
    content: list[dict[str, Any]] = []
    if text:
        content.append({"type": content_type, "text": text})
    for attachment in attachments:
        content.append(serialize_part(attachment))

    return content or ""


@message_to_responses_dict.register
def _(message: SystemMessage) -> dict[str, Any]:
    return {**message.metadata, 'content': message.text or "", 'role': message.role}


@message_to_responses_dict.register
def _(message: ToolMessage) -> dict[str, Any]:
    response = {
        **message.metadata,
        'content': message.text or "",
        'role': message.role,
    }
    if message.tool_call_id:
        response['tool_call_id'] = message.tool_call_id

    return response


@message_to_responses_dict.register
def _(message: UserMessage) -> dict[str, Any]:
    return {
        **message.metadata,
        'content': create_responses_content(message.text, message.attachments, "input_text"),
        'role': message.role,
    }


@message_to_responses_dict.register
def _(message: AssistantMessage) -> dict[str, Any]:
    payload: dict[str, Any] = {
        **message.metadata,
        'content': create_responses_content(message.text, message.attachments, "output_text"),
        'role': message.role,
    }

    tool_calls = [
        {
            "id": call.id,
            "type": "function",
            "function": {
                "name": call.name,
                "arguments": json.dumps(call.arguments, ensure_ascii=False),
            },
        }
        for call in message.tool_calls
    ]
    if tool_calls:
        payload['tool_calls'] = tool_calls
    return payload


class ResponsesPayload(TypedDict, total=False):
    input: list[dict[str, Any]]
    model: str
    temperature: float | None
    max_completion_tokens: int
    stream: bool


class OpenAIResponsesChatProvider(ChatProvider):
    provider = "openai"
    default_path: str = "/responses"

    def __init__(self, base_url: str, api_key: str | None = None):
        super().__init__(base_url, api_key)
        self._stream_buffer: str = ""

    def build_payload(self, messages: Sequence[ChatMessageType], options: ChatRequestOptions) -> ResponsesPayload:
        if options.model is None:
            raise ValueError("Chat options require a model value")

        payload: ResponsesPayload = {
            "input": [message_to_responses_dict(m) for m in messages],
            "model": options.model,
            "temperature": options.temperature,
            "stream": options.stream,
        }

        if options.max_tokens is not None and options.max_tokens > 0:
            payload["max_completion_tokens"] = options.max_tokens
        return payload

    def parse_stream_chunk(self, chunk: bytes) -> Iterable[ChatStreamEvent]:
        events: list[ChatStreamEvent] = []
        self._stream_buffer += chunk.decode("utf-8")

        while "\n\n" in self._stream_buffer:
            raw_event, self._stream_buffer = self._stream_buffer.split("\n\n", 1)
            raw_event = raw_event.strip()
            if not raw_event:
                continue

            event_type = ""
            data_lines: list[str] = []
            for line in raw_event.splitlines():
                if line.startswith("event:"):
                    event_type = line[len("event:") :].strip()
                elif line.startswith("data:"):
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

            if self._is_completion_event(event_type, payload):
                events.append(ChatStreamEvent(done=True, raw=payload))
                continue

            if text := self._extract_responses_delta(event_type, payload):
                events.append(ChatStreamEvent(text=text, raw=payload))

        return events

    @staticmethod
    def _is_completion_event(event_type: str, payload: Mapping[str, Any]) -> bool:
        hinted_type = event_type or (payload.get("type") if isinstance(payload, Mapping) else "")
        return hinted_type == "response.completed"

    @staticmethod
    def _extract_responses_delta(event_type: str, payload: Mapping[str, Any]) -> str | None:
        if not event_type:
            event_type = payload.get("type", "") if isinstance(payload, Mapping) else ""

        if event_type == "response.output_text.delta":
            delta = payload.get("delta")
            if isinstance(delta, Mapping):
                text = delta.get("text")
                if isinstance(text, str):
                    return text
            elif isinstance(delta, str):
                return delta

        if event_type == "response.output_text.done":
            output = payload.get("output")
            if isinstance(output, list) and output:
                first = output[0]
                if isinstance(first, Mapping):
                    content = first.get("content")
                    if isinstance(content, list) and content:
                        entry = content[0]
                        if isinstance(entry, Mapping):
                            text = entry.get("text")
                            if isinstance(text, str):
                                return text
        return None


__all__ = ["OpenAICompletionsChatProvider", "OpenAIResponsesChatProvider"]
