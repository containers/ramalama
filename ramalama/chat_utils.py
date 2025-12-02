from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Mapping, MutableMapping, Protocol

from ramalama.common import perror
from ramalama.config import CONFIG
from ramalama.console import EMOJI, should_colorize

RoleType = Literal["system", "user", "assistant", "tool"]


@dataclass(slots=True)
class TextPart:
    text: str
    type: Literal["text"] = "text"


@dataclass(slots=True)
class ImageURLPart:
    url: str
    detail: str | None = None
    type: Literal["image_url"] = "image_url"


@dataclass(slots=True)
class ImageBytesPart:
    data: bytes
    mime_type: str = "application/octet-stream"
    type: Literal["image_bytes"] = "image_bytes"


@dataclass(slots=True)
class ToolCallPart:
    name: str
    arguments: dict[str, Any]
    type: Literal["tool_call"] = "tool_call"


@dataclass(slots=True)
class ToolResultPart:
    tool_call_id: str
    content: Any
    type: Literal["tool_result"] = "tool_result"


@dataclass(slots=True)
class CustomPart:
    part_type: str
    payload: dict[str, Any]
    type: Literal["custom"] = "custom"


MessagePart = TextPart | ImageURLPart | ImageBytesPart | ToolCallPart | ToolResultPart | CustomPart


@dataclass(slots=True)
class ChatMessage:
    role: RoleType
    parts: list[MessagePart] = field(default_factory=list)
    metadata: MutableMapping[str, Any] = field(default_factory=dict)

    @staticmethod
    def system(text: str) -> "ChatMessage":
        return ChatMessage(role="system", parts=[TextPart(text=text)])

    @staticmethod
    def user(text: str) -> "ChatMessage":
        return ChatMessage(role="user", parts=[TextPart(text=text)])

    @staticmethod
    def assistant(text: str) -> "ChatMessage":
        return ChatMessage(role="assistant", parts=[TextPart(text=text)])

    @staticmethod
    def tool(text: str) -> "ChatMessage":
        return ChatMessage(role="tool", parts=[TextPart(text=text)])


class StreamParser(Protocol):
    def parse_stream_chunk(self, chunk: bytes) -> Iterable[Any]:  # pragma: no cover - protocol definition
        ...


def stream_response(chunks: Iterable[bytes], color: str, provider: StreamParser) -> str:
    color_default = ""
    color_yellow = ""
    if (color == "auto" and should_colorize()) or color == "always":
        color_default = "\033[0m"
        color_yellow = "\033[33m"

    print("\r", end="")
    assistant_response = ""
    for chunk in chunks:
        events = provider.parse_stream_chunk(chunk)
        for event in events:
            text = getattr(event, "text", None)
            if not text:
                continue
            print(f"{color_yellow}{text}{color_default}", end="", flush=True)
            assistant_response += text

    print("")
    return assistant_response


def default_prefix() -> str:
    if not EMOJI:
        return "> "

    if CONFIG.prefix:
        return CONFIG.prefix

    engine = CONFIG.engine

    if engine:
        if os.path.basename(engine) == "podman":
            return "🦭 > "

        if os.path.basename(engine) == "docker":
            return "🐋 > "

    return "🦙 > "


def add_api_key(args, headers=None):
    headers = headers or {}
    if getattr(args, "api_key", None):
        api_key_min = 20
        if len(args.api_key) < api_key_min:
            perror("Warning: Provided API key is invalid.")
        headers["Authorization"] = f"Bearer {args.api_key}"
    return headers


def serialize_part(part: MessagePart) -> dict[str, Any]:
    if isinstance(part, TextPart):
        return {"type": "text", "text": part.text}
    if isinstance(part, ImageURLPart):
        payload: dict[str, Any] = {"url": part.url}
        if part.detail:
            payload["detail"] = part.detail
        return {"type": "image_url", "image_url": payload}
    if isinstance(part, ImageBytesPart):
        return {"type": "image_bytes", "image_bytes": {"data": part.data, "mime_type": part.mime_type}}
    if isinstance(part, ToolCallPart):
        return {"type": "tool_call", "name": part.name, "arguments": dict(part.arguments)}
    if isinstance(part, ToolResultPart):
        return {"type": "tool_result", "tool_call_id": part.tool_call_id, "content": part.content}
    if isinstance(part, CustomPart):
        return {"type": part.part_type, **dict(part.payload)}
    raise TypeError(f"Unsupported message part: {part!r}")


__all__ = [
    "ChatMessage",
    "MessagePart",
    "TextPart",
    "ImageURLPart",
    "ImageBytesPart",
    "ToolCallPart",
    "ToolResultPart",
    "CustomPart",
    "add_api_key",
    "default_prefix",
    "stream_response",
    "serialize_part",
]
