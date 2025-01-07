import os
import pathlib
import urllib.request
from ramalama.common import available, run_cmd, exec_cmd, download_file, verify_checksum, perror
from ramalama.model import Model

missing_huggingface = """
Optional: Huggingface models require the huggingface-cli module.
These modules can be installed via PyPi tools like pip, pip3, pipx, or via
distribution package managers like dnf or apt. Example:
pip install huggingface_hub
"""


def is_huggingface_cli_available():
    """Check if huggingface-cli is available on the system."""
    if available("huggingface-cli"):
        return True
    else:
        return False


def fetch_checksum_from_api(url):
    """Fetch the SHA-256 checksum from the model's metadata API."""
    with urllib.request.urlopen(url) as response:
        data = response.read().decode()
    # Extract the SHA-256 checksum from the `oid sha256` line
    for line in data.splitlines():
        if line.startswith("oid sha256:"):
            return line.split(":", 1)[1].strip()
    raise ValueError("SHA-256 checksum not found in the API response.")


class Huggingface(Model):
    def __init__(self, model):
        model = model.removeprefix("huggingface://")
        model = model.removeprefix("hf://")
        super().__init__(model)
        self.type = "huggingface"
        split = self.model.rsplit("/", 1)
        self.directory = split[0] if len(split) > 1 else ""
        self.filename = split[1] if len(split) > 1 else split[0]
        self.hf_cli_available = is_huggingface_cli_available()

    def login(self, args):
        if not self.hf_cli_available:
            raise NotImplementedError("huggingface-cli not available, skipping login.")
        conman_args = ["huggingface-cli", "login"]
        if args.token:
            conman_args.extend(["--token", args.token])
        self.exec(conman_args, args)

    def logout(self, args):
        if not self.hf_cli_available:
            raise NotImplementedError("huggingface-cli not available, skipping logout.")
        conman_args = ["huggingface-cli", "logout"]
        if args.token:
            conman_args.extend(["--token", args.token])
        self.exec(conman_args, args)

    def pull(self, args):
        model_path = self.model_path(args)
        directory_path = os.path.join(args.store, "repos", "huggingface", self.directory, self.filename)
        os.makedirs(directory_path, exist_ok=True)

        symlink_dir = os.path.dirname(model_path)
        os.makedirs(symlink_dir, exist_ok=True)

        try:
            return self.url_pull(args, model_path, directory_path)
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError) as e:
            if self.hf_cli_available:
                return self.hf_pull(args, model_path, directory_path)
            perror("URL pull failed and huggingface-cli not available")
            raise KeyError(f"Failed to pull model: {str(e)}")

    def hf_pull(self, args, model_path, directory_path):
        conman_args = ["huggingface-cli", "download", "--local-dir", directory_path, self.model]
        run_cmd(conman_args, debug=args.debug)

        relative_target_path = os.path.relpath(directory_path, start=os.path.dirname(model_path))
        pathlib.Path(model_path).unlink(missing_ok=True)
        os.symlink(relative_target_path, model_path)
        return model_path

    def url_pull(self, args, model_path, directory_path):
        # Fetch the SHA-256 checksum from the API
        checksum_api_url = f"https://huggingface.co/{self.directory}/raw/main/{self.filename}"
        try:
            sha256_checksum = fetch_checksum_from_api(checksum_api_url)
        except urllib.error.HTTPError as e:
            raise KeyError(f"failed to pull {checksum_api_url}: " + str(e).strip("'"))
        except urllib.error.URLError as e:
            raise KeyError(f"failed to pull {checksum_api_url}: " + str(e).strip("'"))

        target_path = os.path.join(directory_path, f"sha256:{sha256_checksum}")

        if os.path.exists(target_path) and verify_checksum(target_path):
            relative_target_path = os.path.relpath(target_path, start=os.path.dirname(model_path))
            if not self.check_valid_model_path(relative_target_path, model_path):
                pathlib.Path(model_path).unlink(missing_ok=True)
                os.symlink(relative_target_path, model_path)
            return model_path

        # Download the model file to the target path
        url = f"https://huggingface.co/{self.directory}/resolve/main/{self.filename}"
        download_file(url, target_path, headers={}, show_progress=True)
        if not verify_checksum(target_path):
            print(f"Checksum mismatch for {target_path}, retrying download...")
            os.remove(target_path)
            download_file(url, target_path, headers={}, show_progress=True)
            if not verify_checksum(target_path):
                raise ValueError(f"Checksum verification failed for {target_path}")

        relative_target_path = os.path.relpath(target_path, start=os.path.dirname(model_path))
        if self.check_valid_model_path(relative_target_path, model_path):
            # Symlink is already correct, no need to update it
            return model_path

        pathlib.Path(model_path).unlink(missing_ok=True)
        os.symlink(relative_target_path, model_path)
        return model_path

    def push(self, source, args):
        if not self.hf_cli_available:
            print("huggingface-cli not available, skipping push.")
            return
        proc = run_cmd(
            [
                "huggingface-cli",
                "upload",
                "--repo-type",
                "model",
                self.directory,
                self.filename,
                "--cache-dir",
                os.path.join(args.store, "repos", "huggingface", ".cache"),
                "--local-dir",
                os.path.join(args.store, "repos", "huggingface", self.directory),
            ],
            debug=args.debug,
        )
        return proc.stdout.decode("utf-8")

    def exec(self, cmd_args, args):
        try:
            exec_cmd(cmd_args, debug=args.debug)
        except FileNotFoundError as e:
            print(f"{str(e).strip()}\n{missing_huggingface}")
