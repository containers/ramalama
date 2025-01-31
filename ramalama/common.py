"""ramalama common module."""

import glob
import hashlib
import logging
import os
import random
import re
import shutil
import string
import subprocess
import sys
import time
import urllib.error
import urllib.request

import ramalama.console as console
from ramalama.http_client import HttpClient

logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s")

MNT_DIR = "/mnt/models"
MNT_FILE = f"{MNT_DIR}/model.file"

HTTP_NOT_FOUND = 404
HTTP_RANGE_NOT_SATISFIABLE = 416  # "Range Not Satisfiable" error (file already downloaded)

DEFAULT_IMAGE = "quay.io/ramalama/ramalama"


_engine = -1  # -1 means cached variable not set yet


def get_engine():
    engine = os.getenv("RAMALAMA_CONTAINER_ENGINE")
    if engine is not None:
        return engine

    if available("podman") and (sys.platform != "darwin" or is_podman_machine_running_with_krunkit()):
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


def is_podman_machine_running_with_krunkit():
    podman_machine_list = ["podman", "machine", "list", "--all-providers"]
    try:
        output = run_cmd(podman_machine_list, ignore_stderr=True).stdout.decode("utf-8").strip()
        return re.search("krun.*running", output)
    except subprocess.CalledProcessError:
        pass

    return False


def perror(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def available(cmd):
    return shutil.which(cmd) is not None


def exec_cmd(args, debug=False):
    if debug:
        perror("exec_cmd: ", *args)

    try:
        return os.execvp(args[0], args)
    except Exception:
        perror(f"os.execvp({args[0]}, {args})")
        raise


def run_cmd(args, cwd=None, stdout=subprocess.PIPE, ignore_stderr=False, ignore_all=False, debug=False):
    """
    Run the given command arguments.

    Args:
    args: command line arguments to execute in a subprocess
    cwd: optional working directory to run the command from
    stdout: standard output configuration
    ignore_stderr: if True, ignore standard error
    ignore_all: if True, ignore both standard output and standard error
    debug: if True, print debug information
    """
    if debug:
        perror("run_cmd: ", *args)
        perror(f"Working directory: {cwd}")
        perror(f"Ignore stderr: {ignore_stderr}")
        perror(f"Ignore all: {ignore_all}")

    serr = None
    if ignore_all or ignore_stderr:
        serr = subprocess.DEVNULL

    sout = subprocess.PIPE
    if ignore_all:
        sout = subprocess.DEVNULL

    result = subprocess.run(args, check=True, cwd=cwd, stdout=sout, stderr=serr)
    if debug:
        print("Command finished with return code:", result.returncode)

    return result


def find_working_directory():
    return os.path.dirname(__file__)


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

    # Check if the filename starts with "sha256:"
    fn_base = os.path.basename(filename)
    if not fn_base.startswith("sha256:"):
        raise ValueError(f"filename does not start with 'sha256:': {fn_base}")

    # Extract the expected checksum from the filename
    expected_checksum = fn_base.split(":")[1]
    if len(expected_checksum) != 64:
        raise ValueError("invalid checksum length in filename")

    # Calculate the SHA-256 checksum of the file contents
    sha256_hash = hashlib.sha256()
    with open(filename, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    # Compare the checksums
    return sha256_hash.hexdigest() == expected_checksum


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
                return  # No need to retry

        except urllib.error.URLError as e:
            console.error(f"Network Error: {e.reason}")
            retries += 1

        except TimeoutError:
            retries += 1
            console.warning(f"TimeoutError: The server took too long to respond. Retrying {retries}/{max_retries}...")

        except RuntimeError as e:  # Catch network-related errors from HttpClient
            retries += 1
            console.warning(f"{e}. Retrying {retries}/{max_retries}...")

        except IOError as e:
            retries += 1
            console.warning(f"I/O Error: {e}. Retrying {retries}/{max_retries}...")

        except Exception as e:
            console.error(f"Unexpected error: {str(e)}")
            raise

        if retries >= max_retries:
            error_message = (
                "\nDownload failed after multiple attempts.\n"
                "Possible causes:\n"
                "- Internet connection issue\n"
                "- Server is down or unresponsive\n"
                "- Firewall or proxy blocking the request\n"
            )
            console.error(error_message)
            sys.exit(1)

        time.sleep(2**retries * 0.1)  # Exponential backoff (0.1s, 0.2s, 0.4s...)


def engine_version(engine):
    # Create manifest list for target with imageid
    cmd_args = [engine, "version", "--format", "{{ .Client.Version }}"]
    return run_cmd(cmd_args).stdout.decode("utf-8").strip()


def get_gpu():

    envs = get_env_vars()
    # If env vars already set return
    if envs:
        return

    # ASAHI CASE
    if os.path.exists('/proc/device-tree/compatible'):
        try:
            with open('/proc/device-tree/compatible', 'rb') as f:
                content = f.read().split(b"\0")
                # Check if "apple,arm-platform" is in the content
                if b"apple,arm-platform" in content:
                    os.environ["ASAHI_VISIBLE_DEVICES"] = "1"
        except OSError:
            # Handle the case where the file does not exist
            pass

    # NVIDIA CASE
    try:
        command = ['nvidia-smi']
        run_cmd(command).stdout.decode("utf-8")
        os.environ["CUDA_VISIBLE_DEVICES"] = "0"
        return
    except Exception:
        pass

    # ROCm/AMD CASE
    i = 0
    gpu_num = 0
    gpu_bytes = 0
    for fp in sorted(glob.glob('/sys/bus/pci/devices/*/mem_info_vram_total')):
        with open(fp, 'r') as file:
            content = int(file.read())
            if content > 1073741824 and content > gpu_bytes:
                gpu_bytes = content
                gpu_num = i

        i += 1

    if gpu_bytes:
        os.environ["HIP_VISIBLE_DEVICES"] = str(gpu_num)
        return

    # INTEL iGPU CASE (Look for ARC GPU)
    igpu_num = 0
    for fp in sorted(glob.glob('/sys/bus/pci/drivers/i915/*/device')):
        with open(fp, 'rb') as file:
            content = file.read()
            if b"0x7d55" in content:
                igpu_num += 1

    if igpu_num:
        os.environ["INTEL_VISIBLE_DEVICES"] = str(igpu_num)


def get_env_vars():
    prefixes = ("ASAHI_", "CUDA_", "HIP_", "HSA_", "INTEL_")
    env_vars = {k: v for k, v in os.environ.items() if k.startswith(prefixes)}

    # gpu_type, gpu_num = get_gpu()
    # if gpu_type not in env_vars and gpu_type in {"HIP_VISIBLE_DEVICES", "ASAHI_VISIBLE_DEVICES"}:
    #     env_vars[gpu_type] = str(gpu_num)

    return env_vars
