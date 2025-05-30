"""ramalama common module."""

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
import sysconfig
import time
import urllib.error
from typing import List

import ramalama.console as console
from ramalama.http_client import HttpClient
from ramalama.logger import logger
from ramalama.version import version

MNT_DIR = "/mnt/models"
MNT_FILE = f"{MNT_DIR}/model.file"
MNT_MMPROJ_FILE = f"{MNT_DIR}/mmproj.file"
MNT_FILE_DRAFT = f"{MNT_DIR}/draft_model.file"
MNT_CHAT_TEMPLATE_FILE = f"{MNT_DIR}/chat_template.file"

RAG_DIR = "/rag"
RAG_CONTENT = f"{MNT_DIR}/vector.db"

HTTP_NOT_FOUND = 404
HTTP_RANGE_NOT_SATISFIABLE = 416  # "Range Not Satisfiable" error (file already downloaded)

DEFAULT_IMAGE = "quay.io/ramalama/ramalama"


_engine = -1  # -1 means cached variable not set yet
_nvidia = -1  # -1 means cached variable not set yet
podman_machine_accel = False


def get_engine():
    engine = os.getenv("RAMALAMA_CONTAINER_ENGINE")
    if engine is not None:
        if os.path.basename(engine) == "podman" and sys.platform == "darwin":
            # apple_vm triggers setting global variable podman_machine_accel side effect
            apple_vm(engine)
        return engine

    if os.path.exists("/run/.toolboxenv"):
        return None

    if available("podman") and (sys.platform != "darwin" or apple_vm("podman")):
        return "podman"

    if available("docker") and sys.platform != "darwin":
        return "docker"

    return None


def container_manager():
    global _engine
    if _engine != -1:
        return _engine

    _engine = get_engine()

    return _engine


def confirm_no_gpu(name, provider):
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


def handle_provider(machine):
    global podman_machine_accel
    name = machine.get("Name")
    provider = machine.get("VMType")
    running = machine.get("Running")
    if running:
        if provider == "applehv":
            return confirm_no_gpu(name, provider)
        if "krun" in provider:
            podman_machine_accel = True
            return True

    return None


def apple_vm(engine):
    podman_machine_list = [engine, "machine", "list", "--format", "json", "--all-providers"]
    try:
        machines_json = run_cmd(podman_machine_list, ignore_stderr=True).stdout.decode("utf-8").strip()
        machines = json.loads(machines_json)
        for machine in machines:
            result = handle_provider(machine)
            if result is not None:
                return result
    except subprocess.CalledProcessError:
        pass
    return False


def perror(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def available(cmd):
    return shutil.which(cmd) is not None


def quoted(arr):
    """Return string with quotes around elements containing spaces."""
    return " ".join(['"' + element + '"' if ' ' in element else element for element in arr])


def exec_cmd(args, stdout2null=False, stderr2null=False):
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
    str: Hex digest of the input appended to the prefix sha256:
    """
    h = hashlib.new("sha256")
    h.update(to_hash.encode("utf-8"))
    return f"sha256:{h.hexdigest()}"


def verify_checksum(filename):
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


def download_and_verify(url, target_path, max_retries=2):
    """
    Downloads a file from a given URL and verifies its checksum.
    If the checksum does not match, it retries the download.
    Args:
        url (str): The URL to download from.
        target_path (str): The path to save the downloaded file.
        max_retries (int): Maximum number of retries for download.
    Raises:
        ValueError: If checksum verification fails after multiple attempts.
    """

    for attempt in range(max_retries):
        download_file(url, target_path, headers={}, show_progress=True)
        if verify_checksum(target_path):
            break
        console.warning(
            f"Checksum mismatch for {target_path}, retrying download ... (Attempt {attempt + 1}/{max_retries})"
        )
        os.remove(target_path)
    else:
        raise ValueError(f"Checksum verification failed for {target_path} after multiple attempts")


# default_image function should figure out which GPU the system uses t
# then running appropriate container image.
def default_image():
    image = os.getenv("RAMALAMA_IMAGE")
    if image:
        return image

    return DEFAULT_IMAGE


def genname():
    return "ramalama_" + "".join(random.choices(string.ascii_letters + string.digits, k=10))


def download_file(url, dest_path, headers=None, show_progress=True):
    """
    Downloads a file from a given URL to a specified destination path.

    Args:
        url (str): The URL to download from.
        dest_path (str): The path to save the downloaded file.
        headers (dict): Optional headers to include in the request.
        show_progress (bool): Whether to show a progress bar during download.

    Raises:
        RuntimeError: If the download fails after multiple attempts.
    """
    headers = headers or {}

    # If not running in a TTY, disable progress to prevent CI pollution
    if not sys.stdout.isatty():
        show_progress = False

    http_client = HttpClient()
    max_retries = 5  # Stop after 5 failures
    retries = 0

    while retries < max_retries:
        try:
            # Initialize HTTP client for the request
            http_client.init(url=url, headers=headers, output_file=dest_path, show_progress=show_progress)
            return  # Exit function if successful

        except urllib.error.HTTPError as e:
            if e.code in [HTTP_RANGE_NOT_SATISFIABLE, HTTP_NOT_FOUND]:
                raise e
            retries += 1

        except urllib.error.URLError as e:
            console.error(f"Network Error: {e.reason}")
            retries += 1

        except TimeoutError:
            retries += 1
            console.warning(f"TimeoutError: The server took too long to respond. Retrying {retries}/{max_retries} ...")

        except RuntimeError as e:  # Catch network-related errors from HttpClient
            retries += 1
            console.warning(f"{e}. Retrying {retries}/{max_retries} ...")

        except IOError as e:
            retries += 1
            console.warning(f"I/O Error: {e}. Retrying {retries}/{max_retries} ...")

        except Exception as e:
            console.error(f"Unexpected error: {str(e)}")
            raise e

        if retries >= max_retries:
            error_message = (
                "\nDownload failed after multiple attempts.\n"
                "Possible causes:\n"
                "- Internet connection issue\n"
                "- Server is down or unresponsive\n"
                "- Firewall or proxy blocking the request\n"
            )
            raise ConnectionError(error_message)

        time.sleep(2**retries * 0.1)  # Exponential backoff (0.1s, 0.2s, 0.4s...)


def engine_version(engine):
    # Create manifest list for target with imageid
    cmd_args = [engine, "version", "--format", "{{ .Client.Version }}"]
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


def check_asahi():
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


def check_metal(args):
    if args.container:
        return False
    return platform.system() == "Darwin"


def check_nvidia():
    global _nvidia
    if _nvidia != -1:
        return _nvidia

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

            _nvidia = "cuda"
            return _nvidia

    except Exception:
        _nvidia = ""

    return _nvidia


def check_ascend():
    try:
        command = ['npu-smi', 'info']
        run_cmd(command).stdout.decode("utf-8")
        os.environ["ASCEND_VISIBLE_DEVICES"] = "0"
        return "cann"
    except Exception:
        pass

    return None


def check_rocm_amd():
    gpu_num = 0
    gpu_bytes = 0
    for i, fp in enumerate(sorted(glob.glob('/sys/bus/pci/devices/*/mem_info_vram_total'))):
        with open(fp, 'r') as file:
            content = int(file.read())
            if content > 1073741824 and content > gpu_bytes:
                gpu_bytes = content
                gpu_num = i

    if gpu_bytes:
        os.environ["HIP_VISIBLE_DEVICES"] = str(gpu_num)
        return "hip"

    return None


def check_intel():
    igpu_num = 0
    # Device IDs for select Intel GPUs.  See: https://dgpu-docs.intel.com/devices/hardware-table.html
    intel_gpus = (
        b"0xe20b",
        b"0xe20c",
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


def check_mthreads():
    try:
        command = ['mthreads-gmi']
        run_cmd(command).stdout.decode("utf-8")
        os.environ["MUSA_VISIBLE_DEVICES"] = "0"
        return "musa"
    except Exception:
        pass

    return None


def get_accel():
    if gpu_type := check_asahi():
        return gpu_type

    if gpu_type := check_nvidia():
        return gpu_type

    if gpu_type := check_ascend():
        return gpu_type

    if gpu_type := check_rocm_amd():
        return gpu_type

    if gpu_type := check_intel():
        return gpu_type

    if gpu_type := check_mthreads():
        return gpu_type

    return "none"


def set_accel_env_vars():
    if get_accel_env_vars():
        return

    get_accel()


def get_accel_env_vars():
    gpu_vars = (
        "ASAHI_VISIBLE_DEVICES",
        "ASCEND_VISIBLE_DEVICES",
        "CUDA_VISIBLE_DEVICES",
        "CUDA_LAUNCH_BLOCKING",
        "HIP_VISIBLE_DEVICES",
        "HSA_VISIBLE_DEVICES",
        "HSA_OVERRIDE_GFX_VERSION",
        "INTEL_VISIBLE_DEVICES",
        "MUSA_VISIBLE_DEVICES",
    )
    env_vars = {k: v for k, v in os.environ.items() for gpu_var in gpu_vars if k == gpu_var}

    return env_vars


def rm_until_substring(input, substring):
    pos = input.find(substring)
    if pos == -1:
        return input

    # Create a new string starting after the found substring
    return ''.join(input[i] for i in range(pos + len(substring), len(input)))


def minor_release():
    split = version().split(".")
    vers = ".".join(split[:2])
    if vers == "0":
        vers = "latest"
    return vers


def tagged_image(image):
    if len(image.split(":")) > 1:
        return image
    return f"{image}:{minor_release()}"


def get_cmd_with_wrapper(cmd_arg):
    data_path = sysconfig.get_path("data")
    for dir in ["", f"{data_path}/", "/opt/homebrew/", "/usr/local/", "/usr/"]:
        if os.path.exists(f"{dir}libexec/ramalama/{cmd_arg}"):
            return f"{dir}libexec/ramalama/{cmd_arg}"

    return ""


def check_cuda_version():
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


def select_cuda_image(config):
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
    cuda_image = config['images'].get("CUDA_VISIBLE_DEVICES")

    # Check CUDA version and select appropriate image
    cuda_version = check_cuda_version()

    # Select appropriate image based on CUDA version
    if cuda_version >= (12, 8):
        return cuda_image  # Use the standard image for CUDA 12.8+
    elif cuda_version >= (12, 4):
        return f"{cuda_image}-12.4.1"  # Use the specific version for older CUDA
    else:
        raise RuntimeError(f"CUDA version {cuda_version} is not supported. Minimum required version is 12.4.")


def accel_image(config, args):
    if args and args.image and len(args.image.split(":")) > 1:
        return args.image

    if hasattr(args, 'image_override'):
        return tagged_image(args.image)

    image = os.getenv("RAMALAMA_IMAGE")
    if image:
        return tagged_image(image)

    if config.is_set('image'):
        return tagged_image(config['image'])

    conman = config['engine']
    images = config['images']
    set_accel_env_vars()
    env_vars = get_accel_env_vars()

    if not env_vars:
        gpu_type = None
    else:
        gpu_type, _ = next(iter(env_vars.items()))

    # Get image based on detected GPU type
    image = images.get(gpu_type, config["image"])

    # Special handling for CUDA images based on version - only if the image is the default CUDA image
    cuda_image = images.get("CUDA_VISIBLE_DEVICES")
    if image == cuda_image:
        image = select_cuda_image(config)

    if not args:
        return tagged_image(image)

    if args.runtime == "vllm":
        return "registry.redhat.io/rhelai1/ramalama-vllm"

    if hasattr(args, "rag") and args.rag:
        image += "-rag"

    vers = minor_release()
    if args.container and attempt_to_use_versioned(conman, image, vers, args.quiet):
        return f"{image}:{vers}"

    return f"{image}:latest"


def attempt_to_use_versioned(conman, image, vers, quiet):
    try:
        # check if versioned image exists locally
        if run_cmd([conman, "inspect", f"{image}:{vers}"], ignore_all=True):
            return True

    except Exception:
        pass

    try:
        # attempt to pull the versioned image
        if not quiet:
            print(f"Attempting to pull {image}:{vers} ...")
        run_cmd([conman, "pull", f"{image}:{vers}"], ignore_stderr=True)
        return True

    except Exception:
        return False
