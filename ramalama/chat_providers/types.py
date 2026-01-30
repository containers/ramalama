from typing import Protocol


class ResponseDict(Protocol):
    role: str
    content: str
