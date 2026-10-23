from __future__ import annotations

import glob
import hashlib
import json
import os
import platform
import random
import re
import shutil
import string
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Optional, Union

if TYPE_CHECKING:
    pass

from ramalama.logger import logger
from ramalama.version import version

if TYPE_CHECKING:
    from argparse import Namespace

    from ramalama.arg_types import SUPPORTED_ENGINES
    from ramalama.config import Config
    from ramalama.transports.base import Transport

MNT_DIR = "/mnt/models"
MNT_FILE = f"{MNT_DIR}/model.file"
MNT_MMPROJ_FILE = f"{MNT_DIR}/mmproj.file"
MNT_FILE_DRAFT = f"{MNT_DIR}/draft_model.file"
MNT_CHAT_TEMPLATE_FILE = f"{MNT_DIR}/chat_template.file"

RAG_DIR = "/rag"
RAG_CONTENT = f"{MNT_DIR}/vector.db"


SPLIT_MODEL_PATH_RE = r'(.*?)(?:/)?([^/]*)-00001-of-(\d{5})\.gguf'


def is_split_file_model(model_path):
    """returns true if ends with -%05d-of-%05d.gguf"""
    return bool(re.match(SPLIT_MODEL_PATH_RE, model_path))


def sanitize_filename(filename: str) -> str:
    return filename.replace(":", "-")


podman_machine_accel = False

# CDI device names of the NVIDIA GPUs the user narrowed CUDA_VISIBLE_DEVICES
# down to, set by check_nvidia(). Empty when every detected GPU is in play.
nvidia_selected_devices: list[str] = []


def container_cuda_visible_devices(value: str) -> str:
    """CUDA_VISIBLE_DEVICES as it should read inside the container.

    Where the selection is narrowed, only those GPUs are passed in and the
    container numbers them from zero, so the host's indices no longer describe
    them. Returns the value unchanged when every GPU is in play.
    """
    if not nvidia_selected_devices:
        return value
    return ",".join(str(i) for i in range(len(nvidia_selected_devices)))


def confirm_no_gpu(name, provider) -> bool:
    while True:
        user_input = (
            input(
                f"Warning! Your VM {name} is using {provider}, which does not support GPU. "
                "Only the provider libkrun has GPU support. "
                "See `man ramalama-macos` for more information. "
                "Do you want to proceed without GPU? (yes/no): "
            )
            .strip()
            .lower()
        )
        if user_input in ["yes", "y"]:
            return True
        if user_input in ["no", "n"]:
            return False
        print("Invalid input. Please enter 'yes' or 'no'.")


def handle_provider(machine, config: Optional[Config] = None) -> Optional[bool]:
    global podman_machine_accel
    name = machine.get("Name")
    provider = machine.get("VMType")
    running = machine.get("Running")
    if running:
        if provider == "applehv":
            if config is not None and config.user.no_missing_gpu_prompt:
                return True
            else:
                return confirm_no_gpu(name, provider)
        if "krun" in provider:
            podman_machine_accel = True
            return True

    return None


def apple_vm(engine: SUPPORTED_ENGINES, config: Optional[Config] = None) -> bool:
    podman_machine_list = [*engine_cmd(engine), "machine", "list", "--format", "json"]
    try:
        version = (
            run_cmd([*engine_cmd(engine), "--version"], ignore_stderr=True, encoding="utf-8").stdout.strip().split()
        )
        if len(version) > 1:
            version = version[-1]
        major = int(version.split('.')[0])
        if major < 6:
            podman_machine_list.append("--all-providers")
    except FileNotFoundError:
        # podman is not installed, so there is no podman machine to look for.
        return False
    except (subprocess.CalledProcessError, ValueError, AttributeError) as e:
        logger.warning(f"Failed to parse podman version: {e}")
    try:
        machines_json = run_cmd(podman_machine_list, ignore_stderr=True, encoding="utf-8").stdout.strip()
        machines = json.loads(machines_json)
        for machine in machines:
            result = handle_provider(machine, config)
            if result is not None:
                return result
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError) as e:
        logger.warning(f"Failed to list and parse podman machines: {e}")
    return False


def perror(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


_DEPRECATION_WARNED: set[str] = set()


def warn_deprecated(feature: str, detail: str) -> None:
    """Emit a deprecation warning to stderr, once per feature per process."""
    if feature in _DEPRECATION_WARNED:
        return
    _DEPRECATION_WARNED.add(feature)
    perror(f"Warning: {feature} is deprecated and will be removed in a future RamaLama release. {detail}")


def available(cmd: str) -> bool:
    return shutil.which(cmd) is not None


@lru_cache(maxsize=1)
def in_toolbox() -> bool:
    return os.path.exists("/run/.toolboxenv")


def host_cmd(cmd: Sequence[str]) -> list[str]:
    """Wrap a command so it runs on the host when inside a toolbox.

    Inside a Fedora Toolbox (or similar) environment, host tooling such as the
    container engine, ``nvidia-smi`` or ``nvidia-ctk`` is usually not installed
    in the container. When ``flatpak-spawn`` is available, proxy the command to
    the host via ``flatpak-spawn --host``; otherwise run it unchanged.
    """
    if in_toolbox() and available("flatpak-spawn"):
        return ["flatpak-spawn", "--host", *cmd]
    return list(cmd)


def engine_cmd(engine: str) -> list[str]:
    return host_cmd([engine])


def host_available(cmd: str) -> bool:
    """Check whether ``cmd`` is available, on the host when inside a toolbox."""
    if in_toolbox() and available("flatpak-spawn"):
        try:
            run_cmd(["flatpak-spawn", "--host", "which", cmd], ignore_all=True)
            return True
        except Exception:
            return False
    return available(cmd)


def host_path(path: str) -> str:
    """Map a host absolute path into the toolbox view.

    Toolbox exposes the host root filesystem under ``/run/host``. Configuration
    that lives on the host (e.g. CDI specs in ``/etc/cdi``) is not visible at its
    normal location from inside the container, but is reachable via ``/run/host``.
    """
    if in_toolbox() and path.startswith("/") and os.path.isdir("/run/host"):
        return os.path.join("/run/host", path.lstrip("/"))
    return path


def quoted(arr) -> str:
    """Return string with quotes around elements containing spaces."""
    return " ".join(['"' + element + '"' if ' ' in element else element for element in arr])


def exec_cmd(args, stdout2null: bool = False, stderr2null: bool = False):
    logger.debug(f"exec_cmd: {quoted(args)}")

    stdout_target = subprocess.DEVNULL if stdout2null else None
    stderr_target = subprocess.DEVNULL if stderr2null else None
    try:
        result = subprocess.run(args, stdout=stdout_target, stderr=stderr_target, check=False)
        sys.exit(result.returncode)
    except Exception as e:
        perror(f"Failed to execute {quoted(args)}: {e}")
        raise


def run_cmd(
    args: Sequence[str],
    cwd: Optional[str] = None,
    stdout: Union[int, IO[Any], None] = subprocess.PIPE,
    stdin: Union[int, IO[Any], None] = subprocess.DEVNULL,
    ignore_stderr: bool = False,
    ignore_all: bool = False,
    encoding: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
    timeout: Optional[float] = None,
) -> subprocess.CompletedProcess[Any]:
    """
    Run the given command arguments.

    Args:
    args: command line arguments to execute in a subprocess
    cwd: optional working directory to run the command from
    stdout: standard output configuration
    ignore_stderr: if True, ignore standard error
    ignore_all: if True, ignore both standard output and standard error
    encoding: encoding to apply to the result text
    timeout: if set, raise subprocess.TimeoutExpired after this many seconds
    """
    logger.debug(f"run_cmd: {quoted(args)}")
    logger.debug(f"Working directory: {cwd}")
    logger.debug(f"Ignore stderr: {ignore_stderr}")
    logger.debug(f"Ignore all: {ignore_all}")
    logger.debug(f"env: {env}")

    serr = None
    if ignore_all or ignore_stderr:
        serr = subprocess.DEVNULL

    sout = stdout
    if ignore_all:
        sout = subprocess.DEVNULL

    if env:
        env = os.environ | env

    result = subprocess.run(
        args, check=True, cwd=cwd, stdout=sout, stderr=serr, stdin=stdin, encoding=encoding, env=env, timeout=timeout
    )
    logger.debug(f"Command finished with return code: {result.returncode}")

    return result


def populate_volume_from_image(model: Transport, args: Namespace, output_filename: str, src_model_dir: str = "models"):
    """Builds a Docker-compatible mount string that mirrors Podman image mounts for model assets.

    This function requires the model
    """

    vol_hash = hashlib.sha256(model.model.encode()).hexdigest()[:12]
    volume = f"ramalama-models-{vol_hash}"
    src = f"src-{vol_hash}"

    # Ensure volume exists
    run_cmd([*engine_cmd(args.engine), "volume", "create", volume], ignore_stderr=True)

    # Fresh source container to export from
    run_cmd([*engine_cmd(args.engine), "rm", "-f", src], ignore_stderr=True)
    run_cmd([*engine_cmd(args.engine), "create", "--name", src, model.model])

    try:
        # Stream whole rootfs -> extract only models/<basename>
        export_cmd = [*engine_cmd(args.engine), "export", src]
        untar_cmd = [
            *engine_cmd(args.engine),
            "run",
            "--rm",
            "-i",
            "--mount",
            f"type=volume,src={volume},dst=/mnt",
            "busybox",
            "tar",
            "-C",
            "/mnt",
            "--strip-components=1",
            "-x",
            "-p",
            "-f",
            "-",
            f"{src_model_dir}/{output_filename}",  # NOTE: double check this
        ]

        with (
            subprocess.Popen(export_cmd, stdout=subprocess.PIPE) as p_out,
            subprocess.Popen(untar_cmd, stdin=p_out.stdout) as p_in,
        ):
            p_out.stdout.close()  # type: ignore
            rc_in = p_in.wait()
            rc_out = p_out.wait()
            if rc_in != 0 or rc_out != 0:
                raise subprocess.CalledProcessError(rc_in or rc_out, untar_cmd if rc_in else export_cmd)
    finally:
        run_cmd([*engine_cmd(args.engine), "rm", "-f", src], ignore_stderr=True)

    return volume


def generate_sha256_binary(to_hash: bytes, with_sha_prefix: bool = True) -> str:
    """
    Generates a sha256 for data bytes.

    Args:
    to_hash (bytes): The data to generate the sha256 hash for.

    Returns:
    str: Hex digest of the input appended to the prefix sha256-
    """
    h = hashlib.new("sha256")
    h.update(to_hash)
    if with_sha_prefix:
        return f"sha256-{h.hexdigest()}"
    return h.hexdigest()


def generate_sha256(to_hash: str, with_sha_prefix: bool = True) -> str:
    return generate_sha256_binary(to_hash.encode("utf-8"), with_sha_prefix)


def verify_checksum(filename: str) -> bool:
    """
    Verifies if the SHA-256 checksum of a file matches the checksum provided in
    the filename.

    Args:
    filename (str): The filename containing the checksum prefix
                    (e.g., "sha256:<checksum>")

    Returns:
    bool: True if the checksum matches, False otherwise.
    """

    if not os.path.exists(filename):
        return False

    # Check if the filename starts with "sha256:" or "sha256-" and extract the checksum from filename
    expected_checksum = ""
    fn_base = os.path.basename(filename)
    if fn_base.startswith("sha256:"):
        expected_checksum = fn_base.split(":")[1]
    elif fn_base.startswith("sha256-"):
        expected_checksum = fn_base.split("-")[1]
    else:
        raise ValueError(f"filename has to start with 'sha256:' or 'sha256-': {fn_base}")

    if len(expected_checksum) != 64:
        raise ValueError("invalid checksum length in filename")

    # Calculate the SHA-256 checksum of the file contents
    sha256_hash = hashlib.sha256()
    with open(filename, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    # Compare the checksums
    return sha256_hash.hexdigest() == expected_checksum


def genname(prefix="ramalama-"):
    return prefix + "".join(random.choices(string.ascii_letters + string.digits, k=10))


@lru_cache
def engine_version(engine: SUPPORTED_ENGINES | Path | str) -> SemVer:
    # Create manifest list for target with imageid
    cmd_args = [*engine_cmd(str(engine)), "version", "--format", "{{ .Client.Version }}"]
    return SemVer.parse(run_cmd(cmd_args, encoding="utf-8").stdout.strip())


@lru_cache(maxsize=1)
def in_wsl() -> bool:
    """True when the interpreter itself is running inside a WSL distro.

    False on native Windows, where ramalama drives a podman machine instead.
    """
    try:
        with open("/proc/sys/kernel/osrelease") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False


def is_windows_or_wsl() -> bool:
    """True where containers reach GPUs through WSL rather than native devices.

    Covers both a native Windows interpreter, which runs containers in the
    WSL2-backed podman machine, and ramalama running inside a WSL distro
    itself, which platform.system() reports as "Linux".

    WSL exposes GPUs through /dev/dxg, so Vulkan there means mesa's dzn driver
    translating to D3D12 (no cooperative matrix support, no compute tuning) or
    a silent llvmpipe fallback.
    """
    return platform.system() == "Windows" or in_wsl()


@lru_cache(maxsize=1)
def has_nvidia_vulkan_icd() -> bool:
    """True when NVIDIA's Vulkan ICD manifest is installed on the host.

    The container toolkit injects the ICD from the host driver installation, so
    when it is missing here the vulkan backend finds only mesa's llvmpipe inside
    the container and runs on the CPU instead of failing.
    """
    return any(
        glob.glob(os.path.join(host_path(icd_dir), "*nvidia*.json"))
        for icd_dir in ("/usr/share/vulkan/icd.d", "/etc/vulkan/icd.d")
    )


def rm_until_substring(input: str, substring: str) -> str:
    pos = input.find(substring)
    if pos == -1:
        return input
    return input[pos + len(substring) :]


def minor_release() -> str:
    version_split = version().split(".")
    vers = ".".join(version_split[:2])
    if vers == "0":
        vers = "latest"
    return vers


def version_tagged_image(image: str) -> str:
    if len(image.split(":")) > 1:
        return image
    return f"{image}:{minor_release()}"


def latest_tagged_image(image: str) -> str:
    if len(image.split(":")) > 1:
        return image
    return f"{image}:latest"


def ensure_image(conman: Optional[str], image: str, should_pull: bool = False, quiet: bool = False) -> str:
    """Check if image exists locally; optionally pull it.

    Returns the image string on success. If conman is falsy, returns image unchanged.
    Raises ValueError if the image cannot be pulled.
    """
    if not conman:
        return image

    if ":" not in image:
        image = f"{image}:latest"

    try:
        if run_cmd([*engine_cmd(conman), "inspect", image], ignore_all=True):
            return image
    except Exception:
        pass

    if not should_pull:
        return image

    pull_stdout = subprocess.DEVNULL if quiet else None
    try:
        run_cmd([*engine_cmd(conman), "pull", image], stdout=pull_stdout, ignore_stderr=quiet)
        return image
    except Exception:
        pass

    # This is a fallback for main when the version has been bumped but the
    # tagged image for the version has not been pushed yet
    # Only try this for quay.io/ramalama/ images
    base, _, _ = image.rpartition(":")
    if base and base.startswith("quay.io/ramalama/"):
        latest = latest_tagged_image(base)
        try:
            run_cmd([*engine_cmd(conman), "pull", latest], stdout=pull_stdout, ignore_stderr=quiet)
            return latest
        except Exception as e:
            raise ValueError(f"Failed to pull image {image} or {latest}: {e}")

    raise ValueError(f"Failed to pull image {image}")


class ContainerEntryPoint(str):
    def __init__(self, entrypoint: Optional[str] = None):
        self.entrypoint = entrypoint

    def __str__(self):
        return str(self.entrypoint)

    def __repr__(self):
        return repr(self.entrypoint)


SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>"
    r"(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*"
    r"))?"
    r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


def parse_semver(s: str) -> SemVer:
    m = SEMVER_RE.fullmatch(s)
    if not m:
        raise ValueError(f"Not a valid SemVer 2.0.0: {s!r}")
    major = int(m.group("major"))
    minor = int(m.group("minor"))
    patch = int(m.group("patch"))
    return SemVer(major, minor, patch)


@dataclass(frozen=True, order=True)
class SemVer:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, s: str) -> "SemVer":
        return parse_semver(s)
