"""ramalama common module."""

import glob
import hashlib
import os
import random
import shutil
import string
import subprocess
import sys
import urllib.request
import urllib.error
from ramalama.http_client import HttpClient

x = False
mnt_dir = "/mnt/models"
mnt_file = f"{mnt_dir}/model.file"


def container_manager():
    engine = os.getenv("RAMALAMA_CONTAINER_ENGINE")
    if engine is not None:
        return engine

    if available("podman"):
        if sys.platform != "darwin":
            return "podman"

        podman_machine_list = ["podman", "machine", "list"]
        conman_args = ["podman", "machine", "list", "--format", "{{ .VMType }}"]
        try:
            output = run_cmd(podman_machine_list).stdout.decode("utf-8").strip()
            if "running" not in output:
                return None

            output = run_cmd(conman_args).stdout.decode("utf-8").strip()
            if output == "krunkit" or output == "libkrun":
                return "podman"
            else:
                return None

        except subprocess.CalledProcessError:
            pass

        return "podman"

    if available("docker"):
        return "docker"

    return None


def perror(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def available(cmd):
    return shutil.which(cmd) is not None


def exec_cmd(args, stderr=True, debug=False):
    if debug:
        perror("exec_cmd: ", *args)

    if not stderr:
        # Redirecting stderr to /dev/null
        with open(os.devnull, "w") as devnull:
            os.dup2(devnull.fileno(), sys.stderr.fileno())

    try:
        return os.execvp(args[0], args)
    except Exception:
        perror(f"os.execvp({args[0]}, {args})")
        raise


def run_cmd(args, cwd=None, stdout=subprocess.PIPE, ignore_stderr=False, debug=False):
    """
    Run the given command arguments.

    Args:
    args: command line arguments to execute in a subprocess
    cwd: optional working directory to run the command from
    """
    if debug:
        perror("run_cmd: ", *args)

    stderr = None
    if ignore_stderr:
        stderr = subprocess.PIPE

    return subprocess.run(args, check=True, cwd=cwd, stdout=stdout, stderr=stderr)


def find_working_directory():
    return os.path.dirname(__file__)


def run_curl_cmd(args, filename):
    if not verify_checksum(filename):
        try:
            run_cmd(args)
        except subprocess.CalledProcessError as e:
            if e.returncode == 22:
                perror(filename + " not found")
            raise e


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
    return "quay.io/ramalama/ramalama:latest"


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

    Returns:
        None
    """
    http_client = HttpClient()

    headers = headers or {}

    try:
        http_client.init(url=url, headers=headers, output_file=dest_path, progress=show_progress)
    except urllib.error.HTTPError as e:
        if e.code == 416:  # Range not satisfiable
            if show_progress:
                print(f"File {url} already fully downloaded.")
        else:
            raise e


def engine_version(engine):
    # Create manifest list for target with imageid
    cmd_args = [engine, "version", "--format", "{{ .Client.Version }}"]
    return run_cmd(cmd_args).stdout.decode("utf-8").strip()


def get_gpu():
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

    if gpu_bytes:  # this is the ROCm/AMD case
        return "HIP_VISIBLE_DEVICES", gpu_num

    if os.path.exists('/etc/os-release'):
        with open('/etc/os-release', 'r') as file:
            content = file.read()
            if "asahi" in content.lower():
                return "ASAHI_VISIBLE_DEVICES", 1

    return None, None


def get_env_vars():
    prefixes = ("ASAHI_", "CUDA_", "HIP_", "HSA_")
    env_vars = {k: v for k, v in os.environ.items() if k.startswith(prefixes)}

    gpu_type, gpu_num = get_gpu()
    if gpu_type not in env_vars and gpu_type in {"HIP_VISIBLE_DEVICES", "ASAHI_VISIBLE_DEVICES"}:
        env_vars[gpu_type] = str(gpu_num)

    return env_vars
