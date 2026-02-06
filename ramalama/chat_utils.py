import base64
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from ramalama.console import should_colorize

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
class SystemMessage:
    role: Literal["system"] = "system"
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class UserMessage:
    role: Literal["user"] = "user"
    text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    attachments: list[AttachmentPart] = field(default_factory=list)


@dataclass(slots=True)
class AssistantMessage:
    role: Literal["assistant"] = "assistant"
    text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[ToolCall] = field(default_factory=list)
    attachments: list[AttachmentPart] = field(default_factory=list)


@dataclass(slots=True)
class ToolMessage:
    text: str
    role: Literal["tool"] = "tool"
    metadata: dict[str, Any] = field(default_factory=dict)
    tool_call_id: str | None = None


ChatMessageType = SystemMessage | UserMessage | AssistantMessage | ToolMessage


class StreamParser(Protocol):
    def parse_stream_chunk(self, chunk: bytes) -> Iterable[Any]: ...


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


def serialize_part(part: AttachmentPart) -> dict[str, Any]:
    if isinstance(part, ImageURLPart):
        payload: dict[str, Any] = {"url": part.url}
        if part.detail:
            payload["detail"] = part.detail
        return {"type": "image_url", "image_url": payload}
    if isinstance(part, ImageBytesPart):
        return {
            "type": "image_bytes",
            "image_bytes": {"data": base64.b64encode(part.data).decode("ascii"), "mime_type": part.mime_type},
        }

    raise TypeError(f"Unsupported message part: {part!r}")


__all__ = [
    "ToolCall",
    "ImageURLPart",
    "ImageBytesPart",
    "stream_response",
    "serialize_part",
]
