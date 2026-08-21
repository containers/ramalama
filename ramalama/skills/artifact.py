from __future__ import annotations

import os
import tarfile
import tempfile

from ramalama.common import run_cmd
from ramalama.oci_tools import OciRef
from ramalama.transports.oci import spec as oci_spec

def _tar_skill_dir(path: str) -> str:
    """Tar the skill directory into a temp .tar.gz file, return its path."""
    if not os.path.isdir(path):
        raise ValueError(f"skill directory not found: {path}")
    fd, tar_path = tempfile.mkstemp(suffix=".tar.gz")
    os.close(fd)
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(path, arcname=os.path.basename(os.path.normpath(path)))
    return tar_path


def build_skill_artifact(engine: str, source_dir: str, tag: str, args) -> None:
    """Tar a skill directory and add it as a local OCI artifact."""
    tar_path = _tar_skill_dir(source_dir)
    try:
        filename = os.path.basename(tar_path)
        filepath = oci_spec.normalize_layer_filepath(filename)
        metadata = oci_spec.FileMetadata.from_path(tar_path, name=filename).to_json()

        cmd = [
            engine,
            "artifact",
            "add",
            "--annotation",
            f"{oci_spec.LAYER_ANNOTATION_FILEPATH}={filepath}",
            "--annotation",
            f"{oci_spec.LAYER_ANNOTATION_FILE_METADATA}={metadata}",
            "--replace",
            "--type",
            oci_spec.CNAI_SKILL_ARTIFACT_TYPE,
            tag,
            tar_path,
        ]
        run_cmd(cmd, ignore_stderr=True)
    finally:
        os.remove(tar_path)


def push_skill_artifact(engine: str, tag: str, args) -> None:
    """Push a locally-built skill artifact to a remote registry."""
    ref = OciRef.from_ref_string(tag)
    cmd = [engine, "artifact", "push"]
    if getattr(args, "authfile", None):
        cmd.append(f"--authfile={args.authfile}")
    if str(getattr(args, "tlsverify", True)).lower() == "false":
        cmd.append(f"--tls-verify={args.tlsverify}")
    cmd.append(str(ref))
    run_cmd(cmd, ignore_stderr=getattr(args, "ignore_stderr", False))