from __future__ import annotations

import json
import os
import platform
from collections.abc import Callable
from functools import lru_cache
from typing import TYPE_CHECKING, Literal, Optional, Protocol, TypedDict, Union, cast, get_args

import yaml

from ramalama.common import latest_tagged_image, perror, run_cmd
from ramalama.logger import logger

if TYPE_CHECKING:
    from typing_extensions import TypeAlias

    from ramalama.config import Config

MIN_VRAM_BYTES = 1073741824  # 1GiB


class CDI_DEVICE(TypedDict):
    name: str


class CDI_RETURN_TYPE(TypedDict):
    devices: list[CDI_DEVICE]


def load_cdi_config(spec_dirs: list[str]) -> Optional[CDI_RETURN_TYPE]:
    # Load and merge all CDI configuration files from the given directories.
    # When multiple CDI configs exist (e.g. /var/run/cdi and /etc/cdi), all are
    # merged so that device "all" and other devices are found regardless of
    # which file they appear in (fixes #2485).
    merged_devices: list[CDI_DEVICE] = []
    seen_names: set[str] = set()

    for spec_dir in spec_dirs:
        if not os.path.isdir(spec_dir):
            continue
        for root, _, files in os.walk(spec_dir):
            for file in sorted(files):
                _, ext = os.path.splitext(file)
                if ext not in (".yaml", ".yml", ".json"):
                    continue
                file_path = os.path.join(root, file)
                config = None
                try:
                    with open(file_path, "r") as stream:
                        if ext == ".json":
                            config = json.load(stream)
                        else:
                            config = yaml.safe_load(stream)
                except (OSError, yaml.YAMLError, json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.warning(f"Failed to load/parse CDI file {file_path}: {e}")
                    continue
                if not config or not isinstance(config, dict):
                    continue
                for cdi_device in config.get("devices", []):
                    if isinstance(cdi_device, dict) and (name := cdi_device.get("name")):
                        if name not in seen_names:
                            seen_names.add(name)
                            merged_devices.append(cast(CDI_DEVICE, cdi_device))

    if not merged_devices:
        return None
    return {"devices": merged_devices}


def get_podman_machine_cdi_config() -> Optional[CDI_RETURN_TYPE]:
    cdi_config = run_cmd(["podman", "machine", "ssh", "cat", "/etc/cdi/nvidia.yaml"], encoding="utf-8").stdout.strip()
    if cdi_config:
        return yaml.safe_load(cdi_config)
    return None


def find_in_cdi(devices: list[str]) -> tuple[list[str], list[str]]:
    # Attempts to find a CDI configuration for each device in devices
    # and returns a list of configured devices and a list of
    # unconfigured devices.
    if platform.system() == "Windows":
        cdi = get_podman_machine_cdi_config()
    else:
        cdi = load_cdi_config(['/var/run/cdi', '/etc/cdi'])
    try:
        cdi_devices = cdi.get("devices", []) if cdi else []
        cdi_device_names = [name for cdi_device in cdi_devices if (name := cdi_device.get("name"))]
    except (AttributeError, KeyError, TypeError) as e:
        # Malformed YAML or JSON. Treat everything as unconfigured but warn.
        logger.warning(f"Unable to process CDI configuration: {e}")
        return ([], devices)

    configured = []
    unconfigured = []
    for device in devices:
        if device in cdi_device_names:
            configured.append(device)
        # A device can be specified by a prefix of the uuid
        elif device.startswith("GPU") and any(name.startswith(device) for name in cdi_device_names):
            configured.append(device)
        else:
            perror(f"Device {device} does not have a CDI configuration")
            unconfigured.append(device)

    return configured, unconfigured


def check_asahi() -> Optional[Literal["asahi"]]:
    from ramalama.hw_detect import detect_asahi

    if detect_asahi():
        os.environ["ASAHI_VISIBLE_DEVICES"] = "1"
        return "asahi"
    return None


@lru_cache(maxsize=1)
def check_nvidia() -> Optional[Literal["cuda"]]:
    from ramalama.hw_detect import detect_nvidia

    devices = detect_nvidia()
    if not devices:
        return None

    indices = [str(d.index) for d in devices]
    uuids = [d.uuid for d in devices]

    cuda_visible_devices = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    visible_devices = cuda_visible_devices.split(',') if cuda_visible_devices else []
    for device in visible_devices:
        if device not in indices and not any(uuid.startswith(device) for uuid in uuids):
            perror(f"{device} not found")
            return None

    configured, unconfigured = find_in_cdi(visible_devices + ["all"])

    configured_has_all = "all" in configured
    if unconfigured and not configured_has_all:
        perror(f"No CDI configuration found for {','.join(unconfigured)}")
        perror("You can use the \"nvidia-ctk cdi generate\" command from the ")
        perror("nvidia-container-toolkit to generate a CDI configuration.")
        perror("See ramalama-cuda(7).")
        return None
    elif configured:
        if configured_has_all:
            configured.remove("all")
            if not configured:
                configured = indices

        os.environ["CUDA_VISIBLE_DEVICES"] = ','.join(configured)
        return "cuda"

    return None


def check_ascend() -> Optional[Literal["cann"]]:
    from ramalama.hw_detect import detect_ascend

    if detect_ascend():
        os.environ["ASCEND_VISIBLE_DEVICES"] = "0"
        return "cann"
    return None


def check_rocm_amd() -> Optional[Literal["hip"]]:
    from ramalama.hw_detect import detect_amd_rocm

    devices = detect_amd_rocm()
    if not devices:
        return None

    best = max(
        (d for d in devices if d.memory_bytes > MIN_VRAM_BYTES),
        key=lambda d: d.memory_bytes,
        default=None,
    )
    if best is not None:
        os.environ["HIP_VISIBLE_DEVICES"] = str(best.index)
        return "hip"

    return None


def check_intel() -> Optional[Literal["intel"]]:
    from ramalama.hw_detect import detect_intel

    devices = detect_intel()
    if devices:
        os.environ["INTEL_VISIBLE_DEVICES"] = str(len(devices))
        return "intel"
    return None


def check_mthreads() -> Optional[Literal["musa"]]:
    from ramalama.hw_detect import detect_mthreads

    if detect_mthreads():
        os.environ["MUSA_VISIBLE_DEVICES"] = "0"
        return "musa"
    return None


AccelType: TypeAlias = Literal["asahi", "cuda", "cann", "hip", "intel", "musa"]


@lru_cache(maxsize=1)
def get_accel() -> AccelType | Literal["none"]:
    checks: tuple[Callable[[], Optional[AccelType]], ...] = (
        check_asahi,
        cast(Callable[[], Optional[Literal['cuda']]], check_nvidia),
        check_ascend,
        check_rocm_amd,
        check_intel,
        check_mthreads,
    )
    for check in checks:
        if result := check():
            return result
    return "none"


def set_accel_env_vars():
    if get_accel_env_vars():
        return

    get_accel()


def set_gpu_type_env_vars():
    if get_gpu_type_env_vars():
        return

    get_accel()


GPUEnvVar: TypeAlias = Literal[
    "ASAHI_VISIBLE_DEVICES",
    "ASCEND_VISIBLE_DEVICES",
    "CUDA_VISIBLE_DEVICES",
    "GGML_VK_VISIBLE_DEVICES",
    "HIP_VISIBLE_DEVICES",
    "INTEL_VISIBLE_DEVICES",
    "MUSA_VISIBLE_DEVICES",
]


def get_gpu_devices():
    devices = {}
    for dev in ["dri", "kfd", "accel"]:
        path = "/dev/" + dev
        if os.path.exists(path):
            devices[dev] = path
    return dict(sorted(devices.items()))


def get_gpu_type_env_vars() -> dict[GPUEnvVar, str]:
    return {k: v for k in get_args(GPUEnvVar) if (v := os.environ.get(k))}


AccelEnvVar: TypeAlias = Literal[
    "CUDA_LAUNCH_BLOCKING",
    "HSA_VISIBLE_DEVICES",
    "HSA_OVERRIDE_GFX_VERSION",
    "MTHREADS_VISIBLE_DEVICES",
]


def get_accel_env_vars() -> dict[GPUEnvVar | AccelEnvVar, str]:
    gpu_env_vars: dict[GPUEnvVar, str] = get_gpu_type_env_vars()
    accel_env_vars: dict[AccelEnvVar, str] = {k: v for k in get_args(AccelEnvVar) if (v := os.environ.get(k))}
    return gpu_env_vars | accel_env_vars


class AccelImageArgsWithImage(Protocol):
    image: str


class AccelImageArgsOtherRuntime(Protocol):
    runtime: str
    container: bool
    quiet: bool


class AccelImageArgsOtherRuntimeRAG(Protocol):
    rag: bool
    runtime: str
    container: bool
    quiet: bool


AccelImageArgs: TypeAlias = Union[None, AccelImageArgsOtherRuntime, AccelImageArgsOtherRuntimeRAG]


def accel_image(config: Config, images: Optional[dict[str, str]] = None, conf_key: str = "image") -> str:
    """
    Selects the appropriate image based on config, arguments, environment.
    "images" is a mapping of environment variable names to image names. If not specified,
    the runtime plugin is asked to select the image.
    "conf_key" is the configuration key that holds the configured value of the selected image.
    If not specified, it defaults to "image".

    Never pulls images; callers that need pulling should pass the result to ensure_image().
    """

    # User provided an image via config; tag with :latest if no tag given
    if config.is_set(conf_key):
        return latest_tagged_image(getattr(config, conf_key))

    set_gpu_type_env_vars()
    gpu_type = next(iter(get_gpu_type_env_vars()), "")

    if not images:
        # Ask the runtime plugin to select the image based on detected GPU and its own logic
        from ramalama.plugins.loader import get_runtime

        plugin_image = get_runtime(config.runtime).get_container_image(config, gpu_type)
        if plugin_image is not None:
            return latest_tagged_image(plugin_image)
        images = config.images  # plugin returned None (e.g., MLX); fall back to user dict

    # Explicit images dict provided (e.g., RAG): select by detected GPU type
    return latest_tagged_image(images.get(gpu_type, getattr(config, f"default_{conf_key}")))
