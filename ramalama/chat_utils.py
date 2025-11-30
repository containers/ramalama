from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Mapping, MutableMapping, Protocol

from ramalama.common import perror
from ramalama.config import CONFIG
from ramalama.console import EMOJI, should_colorize

RoleType = Literal["system", "user", "assistant", "tool"]


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
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


AttachmentPart = ImageURLPart | ImageBytesPart


@dataclass(slots=True)
class ChatMessage:
    role: RoleType
    text: str | None = None
    attachments: list[AttachmentPart] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    metadata: MutableMapping[str, Any] = field(default_factory=dict)

    @staticmethod
    def system(text: str) -> "ChatMessage":
        return ChatMessage(role="system", text=text)

    @staticmethod
    def user(text: str) -> "ChatMessage":
        return ChatMessage(role="user", text=text)

    @staticmethod
    def assistant(text: str) -> "ChatMessage":
        return ChatMessage(role="assistant", text=text)

    @staticmethod
    def tool(text: str) -> "ChatMessage":
        return ChatMessage(role="tool", text=text)


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


def serialize_part(part: AttachmentPart) -> dict[str, Any]:
    if isinstance(part, ImageURLPart):
        payload: dict[str, Any] = {"url": part.url}
        if part.detail:
            payload["detail"] = part.detail
        return {"type": "image_url", "image_url": payload}
    if isinstance(part, ImageBytesPart):
        return {"type": "image_bytes", "image_bytes": {"data": part.data, "mime_type": part.mime_type}}
    raise TypeError(f"Unsupported message part: {part!r}")


__all__ = [
    "ChatMessage",
    "ToolCall",
    "ImageURLPart",
    "ImageBytesPart",
    "add_api_key",
    "default_prefix",
    "stream_response",
    "serialize_part",
]
