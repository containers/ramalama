from dataclasses import dataclass
from typing import Literal
ENGINE_TYPES = Literal["podman", "docker"]


@dataclass
class StoreArgs:
    store: str
    use_model_store: bool
    engine: ENGINE_TYPES
    container: bool


@dataclass
class EngineArgs:
    engine: ENGINE_TYPES | None