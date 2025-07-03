"""ramalama common module."""

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
from functools import lru_cache
from typing import TYPE_CHECKING, Callable, List, Literal, Protocol, cast, get_args

import ramalama.amdkfd as amdkfd
from ramalama.logger import logger
from ramalama.version import version

if TYPE_CHECKING:
    from ramalama.arg_types import SUPPORTED_ENGINES, ContainerArgType
    from ramalama.config import Config

MNT_DIR = "/mnt/models"
MNT_FILE = f"{MNT_DIR}/model.file"
MNT_MMPROJ_FILE = f"{MNT_DIR}/mmproj.file"
MNT_FILE_DRAFT = f"{MNT_DIR}/draft_model.file"
MNT_CHAT_TEMPLATE_FILE = f"{MNT_DIR}/chat_template.file"

RAG_DIR = "/rag"
RAG_CONTENT = f"{MNT_DIR}/vector.db"

MIN_VRAM_BYTES = 1073741824  # 1GiB

SPLIT_MODEL_PATH_RE = r'(.*)/([^/]*)-00001-of-(\d{5})\.gguf'


def is_split_file_model(model_path):
    """returns true if ends with -%05d-of-%05d.gguf"""
    return bool(re.match(SPLIT_MODEL_PATH_RE, model_path))


podman_machine_accel = False


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


def handle_provider(machine, config: Config | None = None) -> bool | None:
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


def apple_vm(engine: SUPPORTED_ENGINES, config: Config | None = None) -> bool:
    podman_machine_list = [engine, "machine", "list", "--format", "json", "--all-providers"]
    try:
        machines_json = run_cmd(podman_machine_list, ignore_stderr=True).stdout.decode("utf-8").strip()
        machines = json.loads(machines_json)
        for machine in machines:
            result = handle_provider(machine, config)
            if result is not None:
                return result
    except subprocess.CalledProcessError:
        pass
    return False


def perror(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def available(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def quoted(arr) -> str:
    """Return string with quotes around elements containing spaces."""
    return " ".join(['"' + element + '"' if ' ' in element else element for element in arr])


def exec_cmd(args, stdout2null: bool = False, stderr2null: bool = False):
    logger.debug(f"exec_cmd: {quoted(args)}")
    if stdout2null:
        with open(os.devnull, 'w') as devnull:
            os.dup2(devnull.fileno(), sys.stdout.fileno())

    if stderr2null:
        with open(os.devnull, 'w') as devnull:
            os.dup2(devnull.fileno(), sys.stderr.fileno())

    try:
        return os.execvp(args[0], args)
    except Exception:
        perror(f"os.execvp({args[0]}, {args})")
        raise


def run_cmd(args, cwd=None, stdout=subprocess.PIPE, ignore_stderr=False, ignore_all=False):
    """
    Run the given command arguments.

    Args:
    args: command line arguments to execute in a subprocess
    cwd: optional working directory to run the command from
    stdout: standard output configuration
    ignore_stderr: if True, ignore standard error
    ignore_all: if True, ignore both standard output and standard error
    """
    logger.debug(f"run_cmd: {quoted(args)}")
    logger.debug(f"Working directory: {cwd}")
    logger.debug(f"Ignore stderr: {ignore_stderr}")
    logger.debug(f"Ignore all: {ignore_all}")

    serr = None
    if ignore_all or ignore_stderr:
        serr = subprocess.DEVNULL

    sout = subprocess.PIPE
    if ignore_all:
        sout = subprocess.DEVNULL

    result = subprocess.run(args, check=True, cwd=cwd, stdout=sout, stderr=serr)
    logger.debug(f"Command finished with return code: {result.returncode}")

    return result


def find_working_directory():
    return os.path.dirname(__file__)


def generate_sha256(to_hash: str) -> str:
    """
    Generates a sha256 for a string.

    Args:
    to_hash (str): The string to generate the sha256 hash for.

    Returns:
    str: Hex digest of the input appended to the prefix sha256-
    """
    h = hashlib.new("sha256")
    h.update(to_hash.encode("utf-8"))
    return f"sha256-{h.hexdigest()}"


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


def genname():
    return "ramalama_" + "".join(random.choices(string.ascii_letters + string.digits, k=10))


def engine_version(engine: SUPPORTED_ENGINES) -> str:
    # Create manifest list for target with imageid
    cmd_args = [str(engine), "version", "--format", "{{ .Client.Version }}"]
    return run_cmd(cmd_args).stdout.decode("utf-8").strip()


def resolve_cdi(spec_dirs: List[str]):
    """Loads all CDI specs from the given directories."""
    for spec_dir in spec_dirs:
        for root, _, files in os.walk(spec_dir):
            for file in files:
                if file.endswith('.json') or file.endswith('.yaml'):
                    if load_spec(os.path.join(root, file)):
                        return True

    return False


def yaml_safe_load(stream) -> dict:
    data = {}
    for line in stream:
        if ':' in line:
            key, value = line.split(':', 1)
            data[key.strip()] = value.strip()

    return data


def load_spec(path: str):
    """Loads a single CDI spec file."""
    with open(path, 'r') as f:
        spec = json.load(f) if path.endswith('.json') else yaml_safe_load(f)

    return spec.get('kind')


def check_asahi() -> Literal["asahi"] | None:
    if os.path.exists('/proc/device-tree/compatible'):
        try:
            with open('/proc/device-tree/compatible', 'rb') as f:
                content = f.read().split(b"\0")
                if b"apple,arm-platform" in content:
                    os.environ["ASAHI_VISIBLE_DEVICES"] = "1"
                    return "asahi"
        except OSError:
            pass

    return None


def check_metal(args: ContainerArgType) -> bool:
    if args.container:
        return False
    return platform.system() == "Darwin"


@lru_cache(maxsize=1)
def check_nvidia() -> Literal["cuda"] | None:
    try:
        command = ['nvidia-smi']
        run_cmd(command).stdout.decode("utf-8")

        # ensure at least one CDI device resolves
        if resolve_cdi(['/etc/cdi', '/var/run/cdi']):
            if "CUDA_VISIBLE_DEVICES" not in os.environ:
                dev_command = ['nvidia-smi', '--query-gpu=index', '--format=csv,noheader']
                try:
                    result = run_cmd(dev_command)
                    output = result.stdout.decode("utf-8").strip()
                    if not output:
                        raise ValueError("nvidia-smi returned empty GPU indices")
                    devices = ','.join(output.split('\n'))
                except Exception:
                    devices = "0"

                os.environ["CUDA_VISIBLE_DEVICES"] = devices

            return "cuda"
    except Exception:
        pass

    return None


def check_ascend() -> Literal["cann"] | None:
    try:
        command = ['npu-smi', 'info']
        run_cmd(command).stdout.decode("utf-8")
        os.environ["ASCEND_VISIBLE_DEVICES"] = "0"
        return "cann"
    except Exception:
        pass

    return None


def check_rocm_amd() -> Literal["hip"] | None:
    gpu_num = 0
    gpu_bytes = 0
    for i, (np, props) in enumerate(amdkfd.gpus()):
        # Radeon GPUs older than gfx900 are not supported by ROCm (e.g. Polaris)
        if props['gfx_target_version'] < 90000:
            continue

        mem_banks_count = int(props['mem_banks_count'])
        mem_bytes = 0
        for bank in range(mem_banks_count):
            bank_props = amdkfd.parse_props(np + f'/mem_banks/{bank}/properties')
            # See /usr/include/linux/kfd_sysfs.h for possible heap types
            #
            # Count public and private framebuffer memory as VRAM
            if bank_props['heap_type'] in [amdkfd.HEAP_TYPE_FB_PUBLIC, amdkfd.HEAP_TYPE_FB_PRIVATE]:
                mem_bytes += int(bank_props['size_in_bytes'])

        if mem_bytes > MIN_VRAM_BYTES and mem_bytes > gpu_bytes:
            gpu_bytes = mem_bytes
            gpu_num = i

    if gpu_bytes:
        os.environ["HIP_VISIBLE_DEVICES"] = str(gpu_num)
        return "hip"

    return None


def check_intel() -> Literal["intel"] | None:
    igpu_num = 0
    # Device IDs for select Intel GPUs.  See: https://dgpu-docs.intel.com/devices/hardware-table.html
    intel_gpus = (
        b"0xe20b",
        b"0xe20c",
        b"0x56a0",
        b"0x56a1",
        b"0x7d51",
        b"0x7dd5",
        b"0x7d55",
    )
    # Check to see if any of the device ids in intel_gpus are in the device id of the i915 driver
    for fp in sorted(glob.glob('/sys/bus/pci/drivers/i915/*/device')):
        with open(fp, 'rb') as file:
            content = file.read()
            for gpu_id in intel_gpus:
                if gpu_id in content:
                    igpu_num += 1
    if igpu_num:
        os.environ["INTEL_VISIBLE_DEVICES"] = str(igpu_num)
        return "intel"

    return None


def check_mthreads() -> Literal["musa"] | None:
    try:
        command = ['mthreads-gmi']
        run_cmd(command).stdout.decode("utf-8")
        os.environ["MUSA_VISIBLE_DEVICES"] = "0"
        return "musa"
    except Exception:
        pass

    return None


AccelType = Literal["asahi", "cuda", "cann", "hip", "intel", "musa"]


def get_accel() -> AccelType | Literal["none"]:
    checks: tuple[Callable[[], AccelType | None], ...] = (
        check_asahi,
        cast(Callable[[], Literal['cuda'] | None], check_nvidia),
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


GPUEnvVar = Literal[
    "ASAHI_VISIBLE_DEVICES",
    "ASCEND_VISIBLE_DEVICES",
    "CUDA_VISIBLE_DEVICES",
    "GGML_VK_VISIBLE_DEVICES",
    "HIP_VISIBLE_DEVICES",
    "INTEL_VISIBLE_DEVICES",
    "MUSA_VISIBLE_DEVICES",
]


def get_gpu_type_env_vars() -> dict[GPUEnvVar, str]:
    return {k: os.environ[k] for k in get_args(GPUEnvVar) if k in os.environ}


AccelEnvVar = Literal[
    "CUDA_LAUNCH_BLOCKING",
    "HSA_VISIBLE_DEVICES",
    "HSA_OVERRIDE_GFX_VERSION",
]


def get_accel_env_vars() -> dict[GPUEnvVar | AccelEnvVar, str]:
    gpu_env_vars: dict[GPUEnvVar, str] = get_gpu_type_env_vars()
    accel_env_vars: dict[AccelEnvVar, str] = {k: os.environ[k] for k in get_args(AccelEnvVar) if k in os.environ}
    return gpu_env_vars | accel_env_vars


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


def tagged_image(image: str) -> str:
    if len(image.split(":")) > 1:
        return image
    return f"{image}:{minor_release()}"


def check_cuda_version() -> tuple[int, int]:
    """
    Check the CUDA version installed on the system by parsing the output of nvidia-smi --version.

    Returns:
        tuple: A tuple of (major, minor) version numbers, or (0, 0) if CUDA is not found or version can't be determined.
    """
    try:
        # Run nvidia-smi --version to get version info
        command = ['nvidia-smi']
        output = run_cmd(command).stdout.decode("utf-8").strip()

        # Look for CUDA Version in the output
        cuda_match = re.search(r'CUDA Version\s*:\s*(\d+)\.(\d+)', output)
        if cuda_match:
            major = int(cuda_match.group(1))
            minor = int(cuda_match.group(2))
            return (major, minor)
    except Exception:
        pass

    return (0, 0)


def select_cuda_image(config: Config) -> str:
    """
    Select appropriate CUDA image based on the detected CUDA version.

    Args:
        config: The configuration object containing the CUDA image reference

    Returns:
        str: The appropriate CUDA image name

    Raises:
        RuntimeError: If CUDA version is less than 12.4
    """
    # Get the default CUDA image from config
    cuda_image = config.images.get("CUDA_VISIBLE_DEVICES")

    if cuda_image is None:
        raise RuntimeError("No image repository found for CUDA_VISIBLE_DEVICES in config.")

    # Check CUDA version and select appropriate image
    cuda_version = check_cuda_version()

    # Select appropriate image based on CUDA version
    if cuda_version >= (12, 8):
        return cuda_image  # Use the standard image for CUDA 12.8+
    elif cuda_version >= (12, 4):
        return f"{cuda_image}-12.4.1"  # Use the specific version for older CUDA
    else:
        raise RuntimeError(f"CUDA version {cuda_version} is not supported. Minimum required version is 12.4.")


class AccelImageArgsWithImage(Protocol):
    image: str


class AccelImageArgsVLLMRuntime(Protocol):
    runtime: Literal["vllm"]


class AccelImageArgsOtherRuntime(Protocol):
    runtime: str
    container: bool
    quiet: bool


class AccelImageArgsOtherRuntimeRAG(Protocol):
    rag: bool
    runtime: str
    container: bool
    quiet: bool


AccelImageArgs = None | AccelImageArgsVLLMRuntime | AccelImageArgsOtherRuntime | AccelImageArgsOtherRuntimeRAG


def accel_image(config: Config) -> str:
    """
    Selects and the appropriate image based on config, arguments, environment.
    """
    # User provided an image via config
    if config.is_set("image"):
        return tagged_image(config.image)

    set_gpu_type_env_vars()
    gpu_type = next(iter(get_gpu_type_env_vars()), None)

    # Get image based on detected GPU type
    image = config.images.get(gpu_type or "", config.default_image)  # the or "" is just to keep mypy happy

    # Special handling for CUDA images based on version - only if the image is the default CUDA image
    cuda_image = config.images.get("CUDA_VISIBLE_DEVICES")
    if image == cuda_image:
        image = select_cuda_image(config)

    if config.runtime == "vllm":
        return "registry.redhat.io/rhelai1/ramalama-vllm"

    vers = minor_release()

    should_pull = config.pull in ["always", "missing"]
    if attempt_to_use_versioned(config.engine, image, vers, True, should_pull):
        return f"{image}:{vers}"

    return f"{image}:latest"


def attempt_to_use_versioned(conman: str, image: str, vers: str, quiet: bool, should_pull: bool) -> bool:
    try:
        # check if versioned image exists locally
        if run_cmd([conman, "inspect", f"{image}:{vers}"], ignore_all=True):
            return True

    except Exception:
        pass

    if not should_pull:
        return False

    try:
        # attempt to pull the versioned image
        if not quiet:
            perror(f"Attempting to pull {image}:{vers} ...")
        run_cmd([conman, "pull", f"{image}:{vers}"], ignore_stderr=True)
        return True

    except Exception:
        return False
