import json
import subprocess
from datetime import datetime

import ramalama.annotations as annotations
from ramalama.arg_types import EngineArgType
from ramalama.common import engine_version, run_cmd
from ramalama.logger import logger

ocilabeltype = "org.containers.type"


def convert_from_human_readable_size(input) -> float:
    sizes = [("KB", 1024), ("MB", 1024**2), ("GB", 1024**3), ("TB", 1024**4), ("B", 1)]
    input = input.lower()
    for unit, size in sizes:
        if input.endswith(unit) or input.endswith(unit.lower()):
            return float(input[: -len(unit)]) * size

    return float(input)


def list_artifacts(args: EngineArgType):
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
    models = []
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


def list_manifests(args: EngineArgType):
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

    models = []
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
            models += [
                {
                    "name": manifest["name"],
                    "modified": manifest["modified"],
                    "size": manifest["size"],
                }
            ]
    return models


def list_models(args: EngineArgType):
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
    models = []
    output = run_cmd(conman_args, env={"TZ": "UTC"}).stdout.decode("utf-8").strip()
    if output != "":
        models += json.loads(f"[{output[:-1]}]")
        # exclude dangling images having no tag (i.e. <none>:<none>)
        models = [model for model in models if model["name"] != "oci://<none>:<none>"]

        # Grab the size from the inspect command
        if conman == "docker":
            # grab the size from the inspect command
            for model in models:
                conman_args = [conman, "image", "inspect", model["id"], "--format", "{{.Size}}"]
                output = run_cmd(conman_args).stdout.decode("utf-8").strip()
                # convert the number value from the string output
                model["size"] = int(output)
                # drop the id from the model
                del model["id"]

    models += list_manifests(args)
    models += list_artifacts(args)

    for model in models:
        # Convert to ISO 8601 format
        parsed_date = datetime.fromisoformat(
            model["modified"].replace(" UTC", "").replace("+0000", "+00:00").replace(" ", "T")
        )
        model["modified"] = parsed_date.isoformat()

    return models
