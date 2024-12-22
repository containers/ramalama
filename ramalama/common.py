"""ramalama common module."""

import fcntl
import hashlib
import os
import random
import shutil
import string
import subprocess
import sys
import time
import urllib.request
import urllib.error

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


# The following code is inspired from: https://github.com/ericcurtin/lm-pull/blob/main/lm-pull.py

class File:
    def __init__(self):
        self.file = None
        self.fd = -1

    def open(self, filename, mode):
        self.file = open(filename, mode)
        return self.file

    def lock(self):
        if self.file:
            self.fd = self.file.fileno()
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self.fd = -1
                return 1

        return 0

    def __del__(self):
        if self.fd >= 0:
            fcntl.flock(self.fd, fcntl.LOCK_UN)

        if self.file:
            self.file.close()


class HttpClient:
    def __init__(self):
        pass

    def init(self, url, headers, output_file, progress, response_str=None):
        output_file_partial = None
        if output_file:
            output_file_partial = output_file + ".partial"

        self.file_size = self.set_resume_point(output_file_partial)
        self.printed = False
        if self.urlopen(url, headers):
            return 1

        self.total_to_download = int(self.response.getheader('content-length', 0))
        if response_str is not None:
            response_str.append(self.response.read().decode('utf-8'))
        else:
            out = File()
            if not out.open(output_file_partial, "ab"):
                print("Failed to open file")

                return 1

            if out.lock():
                print("Failed to exclusively lock file")

                return 1

            self.now_downloaded = 0
            self.start_time = time.time()
            self.perform_download(out.file, progress)

        if output_file:
            os.rename(output_file_partial, output_file)

        if self.printed:
            print("\n")

        return 0

    def urlopen(self, url, headers):
        headers["Range"] = f"bytes={self.file_size}-"
        request = urllib.request.Request(url, headers=headers)
        try:
            self.response = urllib.request.urlopen(request)
        except urllib.error.HTTPError as e:
            print(f"Request failed: {e.code}", file=sys.stderr)

            return 1

        if self.response.status not in (200, 206):
            print(f"Request failed: {self.response.status}", file=sys.stderr)

            return 1

        return 0

    def perform_download(self, file, progress):
        self.total_to_download += self.file_size
        self.now_downloaded = 0
        self.start_time = time.time()
        while True:
            data = self.response.read(1024)
            if not data:
                break

            size = file.write(data)
            if progress:
                self.update_progress(size)

    def human_readable_time(self, seconds):
        hrs = int(seconds) // 3600
        mins = (int(seconds) % 3600) // 60
        secs = int(seconds) % 60
        width = 10
        if hrs > 0:
            return f"{hrs}h {mins:02}m {secs:02}s".rjust(width)
        elif mins > 0:
            return f"{mins}m {secs:02}s".rjust(width)
        else:
            return f"{secs}s".rjust(width)

    def human_readable_size(self, size):
        width = 10
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.2f} {unit}".rjust(width)

            size /= 1024

        return f"{size:.2f} PB".rjust(width)

    def get_terminal_width(self):
        return shutil.get_terminal_size().columns

    def generate_progress_prefix(self, percentage):
        return f"{percentage}% |".rjust(6)

    def generate_progress_suffix(self, now_downloaded_plus_file_size, speed, estimated_time):
        return f"{self.human_readable_size(now_downloaded_plus_file_size)}/{self.human_readable_size(self.total_to_download)}{self.human_readable_size(speed)}/s{self.human_readable_time(estimated_time)}"  # noqa: E501

    def calculate_progress_bar_width(self, progress_prefix, progress_suffix):
        progress_bar_width = self.get_terminal_width() - len(progress_prefix) - len(progress_suffix) - 3
        if progress_bar_width < 1:
            progress_bar_width = 1

        return progress_bar_width

    def generate_progress_bar(self, progress_bar_width, percentage):
        pos = (percentage * progress_bar_width) // 100
        progress_bar = ""
        for i in range(progress_bar_width):
            progress_bar += "█" if i < pos else " "

        return progress_bar

    def set_resume_point(self, output_file):
        if output_file and os.path.exists(output_file):
            return os.path.getsize(output_file)

        return 0

    def print_progress(self, progress_prefix, progress_bar, progress_suffix):
        print(f"\r{progress_prefix}{progress_bar}| {progress_suffix}", end="")

    def update_progress(self, chunk_size):
        self.now_downloaded += chunk_size
        now_downloaded_plus_file_size = self.now_downloaded + self.file_size
        percentage = (now_downloaded_plus_file_size * 100) // self.total_to_download if self.total_to_download else 100
        progress_prefix = self.generate_progress_prefix(percentage)
        speed = self.calculate_speed(self.now_downloaded, self.start_time)
        tim = (self.total_to_download - self.now_downloaded) // speed
        progress_suffix = self.generate_progress_suffix(now_downloaded_plus_file_size, speed, tim)
        progress_bar_width = self.calculate_progress_bar_width(progress_prefix, progress_suffix)
        progress_bar = self.generate_progress_bar(progress_bar_width, percentage)
        self.print_progress(progress_prefix, progress_bar, progress_suffix)
        self.printed = True

    def calculate_speed(self, now_downloaded, start_time):
        now = time.time()
        elapsed_seconds = now - start_time
        return now_downloaded / elapsed_seconds


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
