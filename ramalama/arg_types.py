from dataclasses import dataclass
from typing import Literal, Protocol

ENGINE_TYPES = Literal["podman", "docker"]


class EngineArgType(Protocol):
    engine: ENGINE_TYPES | None


@dataclass
class EngineArgs(EngineArgType):
    engine: ENGINE_TYPES | None


class ContainerArgType(Protocol):
    container: bool | None


class StoreArgType(Protocol):
    engine: ENGINE_TYPES | None
    container: bool
    store: str
    use_model_store: bool


@dataclass
class StoreArgs(StoreArgType):
    engine: ENGINE_TYPES | None
    container: bool
    store: str
    use_model_store: bool
