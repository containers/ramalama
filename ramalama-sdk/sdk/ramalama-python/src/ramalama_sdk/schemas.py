from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypedDict


class ChatMessage(TypedDict):
    """Chat completion message payload.

    Attributes:
        role: Message author role.
        content: Message text content.
    """

    role: Literal["system", "user", "assistant", "developer"]
    content: str


@dataclass
class ModelRecord:
    name: str
    last_modified: datetime  # ISO 8601
    size: int  # bytes
