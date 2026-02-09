import json
from dataclasses import dataclass
from datetime import datetime
from typing import TypedDict
import subprocess

import ramalama.annotations as annotations
from ramalama.arg_types import EngineArgType
from ramalama.common import SemVer, engine_version, run_cmd
from ramalama.config import SUPPORTED_ENGINES
from ramalama.transports.oci import spec as oci_spec

ocilabeltype = "org.containers.type"


def convert_from_human_readable_size(input) -> int:
    """
    Convert a human-readable size string (e.g. '1.5MB', '10KB', '42') to a size in bytes.
    The return type is always an integer number of bytes. Fractional values are
    rounded to the nearest integer instead of being truncated, to avoid silently
    losing data (e.g. '1.5MB' is treated as 1_572_864 bytes).
    """
    sizes = [("KB", 1024), ("MB", 1024**2), ("GB", 1024**3), ("TB", 1024**4), ("B", 1)]
    value = str(input).strip()
    lower_value = value.lower()
    for unit, size in sizes:
        if lower_value.endswith(unit.lower()):
            number_part = value[: -len(unit)].strip()
            return int(round(float(number_part) * size))

    return int(round(float(value)))


def parse_datetime(date_str: str) -> datetime | None:
    try:
        parsed_date = datetime.fromisoformat(date_str.replace(" UTC", "").replace("+0000", "+00:00").replace(" ", "T"))
    except ValueError:
        parsed_date = None

    return parsed_date


class ListModelResponse(TypedDict):
    modified: datetime | None
    name: str
    size: int


def list_artifacts(args: EngineArgType):
    if args.engine is None:
        raise ValueError("Cannot list artifacts without a provided engine like podman or docker.")

    if args.engine == "docker":
        return []

    conman_args = [
        args.engine,
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
    try:
        output = run_cmd(conman_args, ignore_stderr=True).stdout.decode("utf-8").strip()
    except Exception:
        return []
    if output == "":
        return []

    try:
        artifacts = json.loads(f"[{output[:-1]}]")
    except json.JSONDecodeError:
        return []

    models = []
    for artifact in artifacts:
        conman_args = [
            args.engine,
            "artifact",
            "inspect",
            artifact["ID"],
        ]
        try:
            output = run_cmd(conman_args, ignore_stderr=True).stdout.decode("utf-8").strip()
        except Exception:
            continue

        if output == "":
            continue
        try:
            inspect = json.loads(output)
        except json.JSONDecodeError:
            continue
        if "Manifest" not in inspect:
            continue
        if "artifactType" not in inspect["Manifest"]:
            continue
        if inspect["Manifest"]['artifactType'] != annotations.ArtifactTypeModelManifest:
            continue
        models.append({
            "name": artifact["name"],
            "modified": parse_datetime(artifact["created"]),
            "size": convert_from_human_readable_size(artifact["size"]),
        })
    return models


def engine_supports_manifest_attributes(engine) -> bool:
    if not engine or engine == "" or engine == "docker":
        return False
    if engine == "podman":
        try:
            if engine_version(engine) < SemVer(5, 0, 0):
                return False
        except Exception:
            return False
    return True


def list_manifests(args: EngineArgType) -> list[ListModelResponse]:
    if args.engine is None:
        raise ValueError("Cannot list manifests without a provided engine like podman or docker.")

    if args.engine == "docker":
        return []

    conman_args = [
        args.engine,
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
    if not engine_supports_manifest_attributes(args.engine):
        return manifests

    models: list[ListModelResponse] = []
    for manifest in manifests:
        conman_args = [
            args.engine,
            "manifest",
            "inspect",
            manifest["ID"],
        ]
        output = run_cmd(conman_args).stdout.decode("utf-8").strip()

        if output == "":
            continue
        inspect = json.loads(output)
        if 'manifests' not in inspect:
            continue
        if not inspect['manifests']:
            continue
        img = inspect['manifests'][0]
        if 'annotations' not in img:
            continue
        if annotations.AnnotationModel in img['annotations']:
            models.append({
                "name": manifest["name"],
                "modified": parse_datetime(manifest["modified"]),
                "size": manifest["size"],
            })
    return models


def list_images(args: EngineArgType) -> list[ListModelResponse]:
    # if engine is docker, size will be retrieved from the inspect command later
    # if engine is podman use "size":{{ .VirtualSize }}
    conman = args.engine
    if conman is None:
        return []

    formatLine = '{"name":"oci://{{ .Repository }}:{{ .Tag }}","modified":"{{ .CreatedAt }}"'
    if conman == "podman":
        formatLine += ',"size":{{ .VirtualSize }}},'
    else:
        formatLine += ',"id":"{{ .ID }}"},'

    conman_args = [
        conman,
        "images",
        "--filter",
        f"label={ocilabeltype}",
        "--format",
        formatLine,
    ]
    if conman == "docker":
        conman_args.insert(2, "--no-trunc")

    output = run_cmd(conman_args, env={"TZ": "UTC"}).stdout.decode("utf-8").strip()
    if output == "":
        return []

    raw = [model for model in json.loads(f"[{output[:-1]}]") if model["name"] != "oci://<none>:<none>"]

    if conman == 'docker':
        ids = [m["id"] for m in raw]
        inspect_args = [conman, "image", "inspect", *ids, "--format", "{{.Id}} {{.Size}}"]
        inspect_out = run_cmd(inspect_args).stdout.decode("utf-8").strip()

        size_by_id: dict[str, str] = {}
        for line in inspect_out.splitlines():
            if not line:
                continue
            image_id, size = line.split(maxsplit=1)
            size_by_id[image_id] = size

        return [
            {
                "name": m["name"],
                "modified": parse_datetime(m["modified"]),
                "size": int(size_by_id[m["id"]]),
            }
            for m in raw
        ]

    return [
        {
            "name": m["name"],
            "modified": parse_datetime(m["modified"]),
            "size": int(m["size"]),
        }
        for m in raw
    ]


def list_models(args: EngineArgType) -> list[ListModelResponse]:
    conman = args.engine
    if conman is None:
        return []

    models = list_images(args)
    models.extend(list_manifests(args))
    models.extend(list_artifacts(args))

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
