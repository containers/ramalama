import json
from dataclasses import dataclass
from datetime import datetime

import ramalama.annotations as annotations
from ramalama.arg_types import EngineArgType
from ramalama.common import engine_version, run_cmd
from ramalama.config import SUPPORTED_ENGINES
from ramalama.transports.oci import spec as oci_spec


def convert_from_human_readable_size(input) -> float:
    sizes = [("KB", 1024), ("MB", 1024**2), ("GB", 1024**3), ("TB", 1024**4), ("B", 1)]
    for unit, size in sizes:
        if input.endswith(unit) or input.endswith(unit.lower()):
            return float(input[: -len(unit)]) * size

    return float(input)


def list_artifacts(args: EngineArgType):
    engine = args.engine
    if engine == "docker" or engine is None:
        return []

    conman_args = [
        engine,
        "artifact",
        "ls",
        "--format",
        (
            '{"name":"oci://{{ .Repository }}:{{ .Tag }}",\
            "created":"{{ .CreatedAt }}", \
            "size":"{{ .Size }}", \
            "ID":"{{ .Digest }}"},'
        ),
    ]
    output = run_cmd(conman_args).stdout.decode("utf-8").strip()
    if output == "":
        return []

    artifacts = json.loads(f"[{output[:-1]}]")
    models = []
    for artifact in artifacts:
        conman_args = [
            engine,
            "artifact",
            "inspect",
            artifact["ID"],
        ]
        output = run_cmd(conman_args).stdout.decode("utf-8").strip()

        if output == "":
            continue
        inspect = json.loads(output)
        if "Manifest" not in inspect:
            continue
        if "artifactType" not in inspect["Manifest"]:
            continue
        if inspect["Manifest"]['artifactType'] != annotations.ArtifactTypeModelManifest:
            continue
        models += [
            {
                "name": artifact["name"],
                "modified": artifact["created"],
                "size": convert_from_human_readable_size(artifact["size"]),
            }
        ]
    return models


def engine_supports_manifest_attributes(engine) -> bool:
    if not engine or engine == "" or engine == "docker":
        return False
    if engine == "podman" and engine_version(engine) < "5":
        return False
    return True


def inspect_manifest(engine: SUPPORTED_ENGINES | str, reference: str) -> dict | None:
    try:
        output = run_cmd([engine, "manifest", "inspect", reference], ignore_stderr=True)
    except Exception:
        return None
    payload = output.stdout.decode("utf-8").strip()
    if payload == "":
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def list_manifests(args: EngineArgType):
    engine = args.engine
    if engine is None:
        raise ValueError("Cannot list manifests without a provided engine like podman or docker.")

    if engine == "docker":
        return []

    conman_args = [
        engine,
        "images",
        "--filter",
        "manifest=true",
        "--format",
        (
            '{"name":"oci://{{ .Repository }}:{{ .Tag }}","modified":"{{ .CreatedAt }}",'
            '"size":{{ .VirtualSize }}, "ID":"{{ .ID }}"},'
        ),
    ]
    output = run_cmd(conman_args).stdout.decode("utf-8").strip()
    if output == "":
        return []

    manifests = json.loads(f"[{output[:-1]}]")
    if not engine_supports_manifest_attributes(engine):
        return manifests

    models = []
    for manifest in manifests:
        ref = manifest["name"].removeprefix("oci://")
        inspect = inspect_manifest(engine, ref)
        if not inspect:
            continue
        if oci_spec.is_cncf_artifact_manifest(inspect):
            models.append(
                {
                    "name": manifest["name"],
                    "modified": manifest["modified"],
                    "size": manifest["size"],
                }
            )
            continue
        for descriptor in inspect.get("manifests") or []:
            if descriptor.get("artifactType") == oci_spec.CNAI_ARTIFACT_TYPE:
                models.append(
                    {
                        "name": manifest["name"],
                        "modified": manifest["modified"],
                        "size": manifest["size"],
                    }
                )
                break
            digest = descriptor.get("digest")
            if not digest:
                continue
            child = inspect_manifest(engine, f"{ref}@{digest}")
            if child and oci_spec.is_cncf_artifact_manifest(child):
                models.append(
                    {
                        "name": manifest["name"],
                        "modified": manifest["modified"],
                        "size": manifest["size"],
                    }
                )
                break
    return models


def list_models(args: EngineArgType):
    conman = args.engine
    if conman is None:
        return []

    models = []
    models += list_manifests(args)
    models += list_artifacts(args)
    for model in models:
        # Convert to ISO 8601 format
        parsed_date = datetime.fromisoformat(
            model["modified"].replace(" UTC", "").replace("+0000", "+00:00").replace(" ", "T")
        )
        model["modified"] = parsed_date.isoformat()

    return models


@dataclass(frozen=True)
class OciRef:
    registry: str
    repository: str
    specifier: str  # Either the digest or the tag
    tag: str | None = None
    digest: str | None = None

    def __str__(self) -> str:
        if self.digest:
            return f"{self.registry}/{self.repository}@{self.digest}"
        return f"{self.registry}/{self.repository}:{self.tag or self.specifier}"

    @staticmethod
    def from_ref_string(ref: str) -> "OciRef":
        return split_oci_reference(ref)


def split_oci_reference(ref: str, default_registry: str = "docker.io") -> OciRef:
    ref = ref.strip()

    name, digest = ref.split("@", 1) if "@" in ref else (ref, None)

    slash = name.rfind("/")
    colon = name.rfind(":")
    if colon > slash:
        name, tag = name[:colon], name[colon + 1 :]
    else:
        tag = None

    parts = name.split("/", 1)
    if len(parts) == 1:
        registry = default_registry
        repository = parts[0]
    else:
        first, rest = parts[0], parts[1]
        if first == "localhost" or "." in first or ":" in first:
            registry = first
            repository = rest
        else:
            registry = default_registry
            repository = name  # keep full path

    specifier = digest or tag
    if specifier is None:
        tag = "latest"
        specifier = tag

    return OciRef(registry=registry, repository=repository, tag=tag, digest=digest, specifier=specifier)
