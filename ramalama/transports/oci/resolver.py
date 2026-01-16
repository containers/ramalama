import os
from collections.abc import Callable
from typing import Literal

from ramalama.common import run_cmd
from ramalama.model_store.store import ModelStore
from ramalama.oci_tools import OciRef
from ramalama.transports.oci import spec as oci_spec
from ramalama.transports.oci.oci_artifact import OCIRegistryClient

ReferenceKind = Literal["artifact", "image", "unknown"]


def _format_oci_reference(oci_ref: OciRef) -> str:
    repository = f"{oci_ref.registry}/{oci_ref.repository}"
    if oci_ref.digest:
        return f"{repository}@{oci_ref.digest}"
    tag = oci_ref.tag or "latest"
    return f"{repository}:{tag}"


def fetch_manifest(oci_ref: OciRef) -> dict | None:
    client = OCIRegistryClient(oci_ref.registry, oci_ref.repository, oci_ref.specifier)
    try:
        manifest, _ = client.get_manifest()
        return manifest
    except Exception:
        return None


def manifest_kind(oci_ref: OciRef) -> ReferenceKind:
    manifest = fetch_manifest(oci_ref)
    if not manifest:
        return "unknown"
    if oci_spec.is_cncf_artifact_manifest(manifest):
        return "artifact"
    return "image"


def engine_artifact_exists(engine: str, oci_ref: OciRef, runner: Callable | None = None) -> bool:
    runner = runner or run_cmd
    try:
        runner([engine, "artifact", "inspect", _format_oci_reference(oci_ref)], ignore_stderr=True)
        return True
    except Exception:
        return False


def engine_image_exists(engine: str, oci_ref: OciRef, runner: Callable | None = None) -> bool:
    runner = runner or run_cmd
    try:
        runner([engine, "image", "inspect", _format_oci_reference(oci_ref)], ignore_stderr=True)
        return True
    except Exception:
        return False


def resolve_engine_kind(engine: str, oci_ref: OciRef, runner: Callable | None = None) -> ReferenceKind:
    if not engine:
        return "unknown"
    engine_name = os.path.basename(engine)
    if engine_name == "podman":
        if engine_artifact_exists(engine, oci_ref, runner=runner):
            return "artifact"
        elif engine_image_exists(engine, oci_ref, runner=runner):
            return "image"

    if engine_name == "docker":
        if engine_image_exists(engine, oci_ref, runner=runner):
            return "image"
    return "unknown"


def model_tag_from_reference(oci_ref: OciRef) -> str:
    return oci_ref.specifier


def model_store_has_snapshot(model_store: ModelStore, oci_ref: OciRef) -> bool:
    model_tag = model_tag_from_reference(oci_ref)
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

    def resolve(self, reference: OciRef) -> ReferenceKind:
        if self.model_store and model_store_has_snapshot(self.model_store, reference):
            return "artifact"

        engine_kind = resolve_engine_kind(self.engine, reference, runner=self.runner)
        if engine_kind != "unknown":
            return engine_kind

        if "." in reference.registry or ":" in reference.registry or reference.registry == "localhost":
            return manifest_kind(reference)
        return "unknown"
