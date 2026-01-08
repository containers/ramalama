import os
from collections.abc import Callable
from typing import Literal, Optional

from ramalama.common import run_cmd
from ramalama.model_store.store import ModelStore
from ramalama.transports.oci import spec as oci_spec
from ramalama.transports.oci.oci_artifact import OCIRegistryClient, _split_reference

ReferenceKind = Literal["artifact", "image", "unknown"]


def normalize_reference(reference: str) -> str:
    return reference.removeprefix("oci://")


def is_registry_reference(reference: str) -> bool:
    reference = normalize_reference(reference)
    host = reference.split("/", 1)[0]
    return "." in host or ":" in host or host == "localhost"


def fetch_manifest(reference: str) -> Optional[dict]:
    reference = normalize_reference(reference)
    if "/" not in reference:
        return None
    registry, remainder = reference.split("/", 1)
    repository, ref = _split_reference(remainder)
    client = OCIRegistryClient(registry, repository, ref)
    try:
        manifest, _ = client.get_manifest()
        return manifest
    except Exception:
        return None


def manifest_kind(reference: str) -> ReferenceKind:
    manifest = fetch_manifest(reference)
    if not manifest:
        return "unknown"
    if oci_spec.is_cnai_artifact_manifest(manifest):
        return "artifact"
    return "image"


def engine_artifact_exists(engine: str, reference: str, runner: Callable | None = None) -> bool:
    runner = runner or run_cmd
    try:
        runner([engine, "artifact", "inspect", reference], ignore_stderr=True)
        return True
    except Exception:
        return False


def engine_image_exists(engine: str, reference: str, runner: Callable | None = None) -> bool:
    runner = runner or run_cmd
    try:
        runner([engine, "image", "inspect", reference], ignore_stderr=True)
        return True
    except Exception:
        return False


def resolve_engine_kind(engine: str, reference: str, runner: Callable | None = None) -> ReferenceKind:
    if not engine:
        return "unknown"
    engine_name = os.path.basename(engine)
    if engine_name == "podman":
        if engine_artifact_exists(engine, reference, runner=runner):
            return "artifact"
        elif engine_image_exists(engine, reference, runner=runner):
            return "image"

    if engine_name == "docker":
        if engine_image_exists(engine, reference, runner=runner):
            return "image"
    return "unknown"


def model_tag_from_reference(reference: str) -> str:
    normalized = normalize_reference(reference)
    ref = normalized.split("/", 1)[1] if "/" in normalized else normalized
    if "@" in ref:
        return ref.split("@", 1)[1]
    if ":" in ref.rsplit("/", 1)[-1]:
        return ref.rsplit(":", 1)[1]
    return "latest"


def model_store_has_snapshot(model_store: ModelStore, reference: str) -> bool:
    model_tag = model_tag_from_reference(reference)
    try:
        _, cached_files, complete = model_store.get_cached_files(model_tag)
        return complete and bool(cached_files)
    except Exception:
        return False


class OCITypeResolver:
    def __init__(self, engine: str, model_store: ModelStore | None = None, runner: Callable | None = None):
        self.engine = engine
        self.model_store = model_store
        self.runner = runner or run_cmd

    def resolve(self, reference: str) -> ReferenceKind:
        if self.model_store and model_store_has_snapshot(self.model_store, reference):
            return "artifact"

        engine_kind = resolve_engine_kind(self.engine, reference, runner=self.runner)
        if engine_kind != "unknown":
            return engine_kind
        if is_registry_reference(reference):
            return manifest_kind(reference)
        return "unknown"
