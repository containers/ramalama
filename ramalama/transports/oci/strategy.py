import os
from pathlib import Path
from typing import Literal, TypedDict, cast

from ramalama.common import SemVer, engine_version
from ramalama.config import CONFIG, SUPPORTED_ENGINES
from ramalama.model_store.store import ModelStore
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


class EngineStrategy:
    """Resolve reference kind and return the appropriate strategy implementation."""

    def __init__(
        self,
        engine: SUPPORTED_ENGINES | Path | str | None,
        *,
        model_store: ModelStore | None = None,
    ):
        if (engine := engine or CONFIG.engine) is None:
            raise Exception("EngineStrategies require a valid engine")

        self.engine = str(engine)
        self.model_store = model_store
        self._type_resolver = oci_resolver.OCITypeResolver(self.engine, model_store=self.model_store)

        engine_name = cast(SUPPORTED_ENGINES, os.path.basename(self.engine))
        self.strategies: StrategiesType = {
            "image": get_engine_image_strategy(self.engine, engine_name)(
                self.engine,
                model_store=self.model_store,
            ),
            "artifact": get_engine_artifact_strategy(self.engine, engine_name)(
                self.engine,
                model_store=self.model_store,
            ),
        }

    def resolve_kind(self, model: str) -> Literal["image", "artifact"] | None:
        kind = self._type_resolver.resolve(model)
        if kind == "unknown":
            return None
        return kind

    def resolve(self, model: str) -> BaseArtifactStrategy | BaseImageStrategy:
        kind = self.resolve_kind(model)
        if kind is None:
            raise Exception(f"Could not identify an artifact type for {model}")

        return self.strategies[kind]
