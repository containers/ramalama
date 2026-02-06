import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, TypedDict, cast

from ramalama.common import SemVer, engine_version
from ramalama.config import SUPPORTED_ENGINES, get_config
from ramalama.model_store.store import ModelStore
from ramalama.oci_tools import OciRef
from ramalama.transports.oci import resolver as oci_resolver
from ramalama.transports.oci.strategies import (
    BaseArtifactStrategy,
    BaseImageStrategy,
    DockerImageStrategy,
    HttpArtifactStrategy,
    PodmanArtifactStrategy,
    PodmanImageStrategy,
)

PODMAN_MIN_ARTIFACT_VERSION = SemVer(5, 7, 0)


def get_engine_image_strategy(engine: str, engine_name: SUPPORTED_ENGINES) -> type[BaseImageStrategy]:
    if engine_name == "docker":
        return DockerImageStrategy
    elif engine_name == "podman":
        return PodmanImageStrategy
    else:
        raise ValueError(f"No engine image strategies for `{engine_name}` engine.")


def get_engine_artifact_strategy(engine: str, engine_name: SUPPORTED_ENGINES) -> type[BaseArtifactStrategy]:
    if engine_name == "podman":
        version = SemVer.parse(engine_version(engine))
        if version >= PODMAN_MIN_ARTIFACT_VERSION:
            return PodmanArtifactStrategy

    return HttpArtifactStrategy


class StrategiesType(TypedDict):
    image: BaseImageStrategy
    artifact: BaseArtifactStrategy


@lru_cache
def get_strategy(
    engine: str, engine_name: SUPPORTED_ENGINES, model_store: ModelStore, kind: Literal['image', 'artifact']
) -> BaseArtifactStrategy | BaseImageStrategy:
    cls_generator = get_engine_image_strategy if kind == 'image' else get_engine_artifact_strategy
    cls = cls_generator(engine, engine_name)
    return cls(engine=engine, model_store=model_store)


class OCIStrategyFactory:
    """Resolve reference kind and return the appropriate strategy implementation."""

    def __init__(
        self,
        engine: SUPPORTED_ENGINES | Path | str | None,
        model_store: ModelStore,
    ):
        if (engine := engine or get_config().engine) is None:
            raise Exception("OCIStrategyFactory require a valid engine")

        self.engine = str(engine)
        self.engine_name: SUPPORTED_ENGINES = cast(SUPPORTED_ENGINES, os.path.basename(self.engine))
        self.model_store = model_store
        self._type_resolver = oci_resolver.OCITypeResolver(self.engine, model_store=self.model_store)

    def strategies(self, kind: Literal['image', 'artifact']) -> BaseArtifactStrategy | BaseImageStrategy:
        return get_strategy(self.engine, self.engine_name, self.model_store, kind)

    def resolve_kind(self, model: OciRef) -> Literal["image", "artifact"] | None:
        kind = self._type_resolver.resolve(model)
        if kind == "unknown":
            return None
        return kind

    def resolve(self, model: OciRef) -> BaseArtifactStrategy | BaseImageStrategy:
        kind = self.resolve_kind(model)
        if kind is None:
            raise Exception(f"Could not identify an artifact type for {model}")

        return self.strategies(kind)
