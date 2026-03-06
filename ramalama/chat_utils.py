import base64
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from ramalama.console import should_colorize

# Strip ANSI escape sequences and control chars to prevent terminal injection (e.g. from LLM output)
_ANSI_ESCAPE_RE = re.compile(
    r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x1b]*(?:\x1b\\|\x07))"
)
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_for_terminal(text: str) -> str:
    """Remove ANSI escape sequences and control characters from untrusted output before printing."""
    if not text:
        return text
    s = _ANSI_ESCAPE_RE.sub("", text)
    return _CONTROL_CHARS_RE.sub("", s)

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
            safe_text = sanitize_for_terminal(text)
            print(f"{color_yellow}{safe_text}{color_default}", end="", flush=True)
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
    "sanitize_for_terminal",
    "stream_response",
    "serialize_part",
]
