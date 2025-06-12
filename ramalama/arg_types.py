from dataclasses import dataclass
from typing import Protocol

from ramalama.config import SUPPORTED_ENGINES


class EngineArgType(Protocol):
    engine: SUPPORTED_ENGINES | None


@dataclass
class EngineArgs(EngineArgType):
    engine: SUPPORTED_ENGINES | None


class ContainerArgType(Protocol):
    container: bool | None


class StoreArgType(Protocol):
    engine: SUPPORTED_ENGINES | None
    container: bool
    store: str
    use_model_store: bool


@dataclass
class StoreArgs(StoreArgType):
    engine: SUPPORTED_ENGINES | None
    container: bool
    store: str
    use_model_store: bool
