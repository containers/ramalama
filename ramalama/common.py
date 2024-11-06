"""ramalama common module."""

import hashlib
import os
import random
import shutil
import string
import subprocess
import sys
import urllib.request

x = False
mnt_dir = "/mnt/models"
mnt_file = f"{mnt_dir}/model.file"


def in_container():
    if os.path.exists("/run/.containerenv") or os.path.exists("/.dockerenv") or os.getenv("container"):
        return True

    return False


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
    try:
        from tqdm import tqdm
    except FileNotFoundError:
        raise NotImplementedError(
            """\
Ollama models requires the tqdm modules.
This module can be installed via PyPi tools like pip, pip3, pipx or via
distribution package managers like dnf or apt. Example:
pip install tqdm
"""
        )

    # Check if partially downloaded file exists
    if os.path.exists(dest_path):
        downloaded_size = os.path.getsize(dest_path)
    else:
        downloaded_size = 0

    request = urllib.request.Request(url, headers=headers or {})
    request.headers["Range"] = f"bytes={downloaded_size}-"  # Set range header

    filename = dest_path.split('/')[-1]

    bar_format = "Pulling {desc}: {percentage:3.0f}% ▕{bar:20}▏ {n_fmt}/{total_fmt} {rate_fmt} {remaining}"
    try:
        with urllib.request.urlopen(request) as response:
            total_size = int(response.headers.get("Content-Length", 0)) + downloaded_size
            chunk_size = 8192  # 8 KB chunks

            with open(dest_path, "ab") as file:
                if show_progress:
                    with tqdm(
                        desc=filename,
                        total=total_size,
                        initial=downloaded_size,
                        unit="B",
                        unit_scale=True,
                        unit_divisor=1024,
                        bar_format=bar_format,
                        ascii=True,
                    ) as progress_bar:
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break
                            file.write(chunk)
                            progress_bar.update(len(chunk))
                else:
                    # Download file without showing progress
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        file.write(chunk)
    except urllib.error.HTTPError as e:
        if e.code == 416:
            if show_progress:
                # If we get a 416 error, it means the file is fully downloaded
                print(f"File {url} already fully downloaded.")
        else:
            raise e
