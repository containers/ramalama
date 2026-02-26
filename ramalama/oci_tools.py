import json
import subprocess
from datetime import datetime
from typing import TypedDict

import ramalama.annotations as annotations
from ramalama.arg_types import EngineArgType
from ramalama.common import engine_version, run_cmd
from ramalama.logger import logger

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
        if (output := run_cmd(conman_args, ignore_stderr=True).stdout.decode("utf-8").strip()) == "":
            return []
    except subprocess.CalledProcessError as e:
        logger.debug(e)
        return []

    artifacts = json.loads(f"[{output[:-1]}]")
    models: list[ListModelResponse] = []
    for artifact in artifacts:
        conman_args = [
            args.engine,
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
        models.append(
            {
                "name": artifact["name"],
                "modified": parse_datetime(artifact["created"]),
                "size": convert_from_human_readable_size(artifact["size"]),
            }
        )
    return models


def engine_supports_manifest_attributes(engine) -> bool:
    if not engine or engine == "" or engine == "docker":
        return False
    if engine == "podman" and engine_version(engine) < "5":
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
            models.append(
                {
                    "name": manifest["name"],
                    "modified": parse_datetime(manifest["modified"]),
                    "size": manifest["size"],
                }
            )
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
