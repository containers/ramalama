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
    sizes = [("KB", 1024), ("MB", 1024**2), ("GB", 1024**3), ("TB", 1024**4), ("B", 1)]
    input = input.lower()
    for unit, size in sizes:
        if input.endswith(unit) or input.endswith(unit.lower()):
            return int(float(input[: -len(unit)]) * size)

    return int(input)


def isoformat_string(date_str: str) -> datetime | None:
    try:
        parsed_date = datetime.fromisoformat(date_str.replace(" UTC", "").replace("+0000", "+00:00").replace(" ", "T"))
    except ValueError:
        parsed_date = None

    return parsed_date


class ListModelResponse(TypedDict):
    modified: datetime | None
    name: str
    size: int


def list_artifacts(args: EngineArgType) -> list[ListModelResponse]:
    if args.engine is None:
        raise ValueError("Cannot list artifacts without a provided engine like podman or docker.")

    if args.engine == "docker":
        return []

    conman_args = [
        args.engine,
        "artifact",
        "ls",
        "--format",
        ('{"name":"oci://{{ .Repository }}:{{ .Tag }}",\
            "created":"{{ .CreatedAt }}", \
            "size":"{{ .Size }}", \
            "ID":"{{ .Digest }}"},'),
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
                "modified": isoformat_string(artifact["created"]),
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
                    "modified": isoformat_string(manifest["modified"]),
                    "size": manifest["size"],
                }
            )
    return models


def list_models(args: EngineArgType) -> list[ListModelResponse]:
    conman = args.engine
    if conman is None:
        return []

    # if engine is docker, size will be retrieved from the inspect command later
    # if engine is podman use "size":{{ .VirtualSize }}
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
    oci_models = []
    output = run_cmd(conman_args, env={"TZ": "UTC"}).stdout.decode("utf-8").strip()
    if output != "":
        # exclude dangling images having no tag (i.e. <none>:<none>)
        oci_models = [model for model in json.loads(f"[{output[:-1]}]") if model["name"] != "oci://<none>:<none>"]

        # Grab the size from the inspect command
        if conman == "docker":
            # grab the size from the inspect command
            for model in oci_models:
                conman_args = [conman, "image", "inspect", model["id"], "--format", "{{.Size}}"]
                output = run_cmd(conman_args).stdout.decode("utf-8").strip()
                # convert the number value from the string output
                model["size"] = int(output)
                # drop the id from the model
                del model["id"]

    models: list[ListModelResponse] = oci_models
    models.extend(list_manifests(args))
    models.extend(list_artifacts(args))

    return models
