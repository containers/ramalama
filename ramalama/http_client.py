# The following code is inspired from: https://github.com/ericcurtin/lm-pull/blob/main/lm-pull.py

import os
import shutil
import sys
import time
import urllib.request

import ramalama.console as console
from ramalama.common import perror, verify_checksum
from ramalama.file import File
from ramalama.logger import logger

HTTP_NOT_FOUND = 404
HTTP_RANGE_NOT_SATISFIABLE = 416  # "Range Not Satisfiable" error (file already downloaded)


class HttpClient:
    def __init__(self):
        pass

    def init(self, url, headers, output_file, show_progress, response_str=None):
        output_file_partial = None
        if output_file:
            output_file_partial = output_file + ".partial"

        self.file_size = self.set_resume_point(output_file_partial)
        self.urlopen(url, headers)
        self.total_to_download = int(self.response.getheader('content-length', 0))
        if response_str is not None:
            response_str.append(self.response.read().decode('utf-8'))
        else:
            out = File()
            if not out.open(output_file_partial, "ab"):
                raise IOError("Failed to open file")

            if out.lock():
                raise IOError("Failed to exclusively lock file")

            self.now_downloaded = 0
            self.start_time = time.time()
            self.perform_download(out.file, show_progress)

        if output_file:
            os.rename(output_file_partial, output_file)

    def urlopen(self, url, headers):
        headers["Range"] = f"bytes={self.file_size}-"
        logger.debug(f"Running urlopen {url} with headers: {headers}")
        request = urllib.request.Request(url, headers=headers)
        self.response = urllib.request.urlopen(request)

        if self.response.status not in (200, 206):
            raise IOError(f"Request failed: {self.response.status}")

    def perform_download(self, file, show_progress):
        self.total_to_download += self.file_size
        self.now_downloaded = 0
        self.start_time = time.time()
        accumulated_size = 0
        last_update_time = time.time()
        while True:
            data = self.response.read(1024)
            if not data:
                return

            size = file.write(data)
            if show_progress:
                accumulated_size += size
                if time.time() - last_update_time >= 0.1:
                    self.update_progress(accumulated_size)
                    accumulated_size = 0
                    last_update_time = time.time()

        if accumulated_size > 0:
            self.update_progress(accumulated_size)

        if show_progress:
            perror("\033[K", end="\r")

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
        perror(f"\r{progress_prefix}{progress_bar}| {progress_suffix}", end="")

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

    def calculate_speed(self, now_downloaded, start_time):
        now = time.time()
        elapsed_seconds = now - start_time
        return now_downloaded / elapsed_seconds


def download_file(url: str, dest_path: str, headers: dict[str, str] | None = None, show_progress: bool = True):
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

        except KeyboardInterrupt:
            perror("\nDownload interrupted by user. Exiting cleanly.")
            raise

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


def download_and_verify(url: str, target_path: str, max_retries: int = 2):
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
