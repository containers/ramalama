"""ramalama common module."""

import hashlib
import os
import shutil
import subprocess
import sys

x = False


def in_container():
    if os.path.exists("/run/.containerenv") or os.path.exists("/.dockerenv") or os.getenv("container"):
        return True

    return False


def container_manager():
    if available("podman"):
        return "podman"

    if available("docker"):
        return "docker"

    return ""


def perror(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def available(cmd):
    return shutil.which(cmd) is not None


def exec_cmd(args):
    if x:
        print(*args)

    try:
        return os.execvp(args[0], args)
    except Exception:
        perror(f"os.execvp({args[0]}, {args})")
        raise


def run_cmd(args):
    if x:
        print(*args)

    return subprocess.run(args, check=True, stdout=subprocess.PIPE)


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
