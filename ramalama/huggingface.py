import os
import pathlib
import urllib.request
from ramalama.common import available, run_cmd, exec_cmd, download_file, verify_checksum, perror, generate_sha256
from ramalama.model import Model, rm_until_substring
from ramalama.model_store import ModelRegistry, SnapshotFile

missing_huggingface = """
Optional: Huggingface models require the huggingface-cli module.
These modules can be installed via PyPi tools like pip, pip3, pipx, or via
distribution package managers like dnf or apt. Example:
pip install huggingface_hub
"""


def is_huggingface_cli_available():
    """Check if huggingface-cli is available on the system."""
    return available("huggingface-cli")

def fetch_checksum_from_api(organization, file):
    """Fetch the SHA-256 checksum from the model's metadata API."""
    checksum_api_url = f"https://huggingface.co/{organization}/raw/main/{file}"
    try:
        with urllib.request.urlopen(checksum_api_url) as response:
            data = response.read().decode()
        # Extract the SHA-256 checksum from the `oid sha256` line
        for line in data.splitlines():
            if line.startswith("oid sha256:"):
                return line.replace("oid", "").strip()
        raise ValueError("SHA-256 checksum not found in the API response.")
    except urllib.error.HTTPError as e:
        raise KeyError(f"failed to pull {checksum_api_url}: " + str(e).strip("'"))
    except urllib.error.URLError as e:
        raise KeyError(f"failed to pull {checksum_api_url}: " + str(e).strip("'"))

class Huggingface(Model):
    def __init__(self, model, store_path=""):
        model = rm_until_substring(model, "hf.co/")
        model = rm_until_substring(model, "://")
        super().__init__(model, store_path, ModelRegistry.HUGGINGFACE)

        self.hf_cli_available = is_huggingface_cli_available()

    def login(self, args):
        if not self.hf_cli_available:
            raise NotImplementedError(missing_huggingface)
        conman_args = ["huggingface-cli", "login"]
        if args.token:
            conman_args.extend(["--token", args.token])
        self.exec(conman_args, args)

    def logout(self, args):
        if not self.hf_cli_available:
            raise NotImplementedError(missing_huggingface)
        conman_args = ["huggingface-cli", "logout"]
        if args.token:
            conman_args.extend(["--token", args.token])
        self.exec(conman_args, args)

    def pull(self, debug = False):
        hash, cached_files, all = self.store.get_cached_files(self.model_tag)
        if all:
            return self.store.get_snapshot_file_path(hash, self.filename)

        # Fetch the SHA-256 checksum of model from the API and use as snapshot hash
        snapshot_hash = fetch_checksum_from_api(self.store.model_organization, self.store.model_name)
        
        blob_url = f"https://huggingface.co/{self.store.model_organization}/resolve/main"
        headers = {}

        files: list[SnapshotFile] = []
        model_file_name = self.store.model_name
        config_file_name = "config.json"
        generation_config_file_name = "generation_config.json"
        tokenizer_config_file_name = "tokenizer_config.json"

        if model_file_name not in cached_files:
            files.append(
                SnapshotFile(
                    url=f"{blob_url}/{model_file_name}",
                    header=headers,
                    hash=snapshot_hash,
                    name=model_file_name,
                    should_show_progress=True,
                    should_verify_checksum=True,
                )
            )
        if config_file_name not in cached_files:
            files.append(
                SnapshotFile(
                    url=f"{blob_url}/{config_file_name}",
                    header=headers,
                    hash=generate_sha256(config_file_name),
                    name=config_file_name,
                    should_show_progress=False,
                    should_verify_checksum=False,
                    required=False,
                )
            )
        if generation_config_file_name not in cached_files:
            files.append(
                SnapshotFile(
                    url=f"{blob_url}/{generation_config_file_name}",
                    header=headers,
                    hash=generate_sha256(generation_config_file_name),
                    name=generation_config_file_name,
                    should_show_progress=False,
                    should_verify_checksum=False,
                    required=False,
                )
            )
        if tokenizer_config_file_name not in cached_files:
            files.append(
                SnapshotFile(
                    url=f"{blob_url}/{tokenizer_config_file_name}",
                    header=headers,
                    hash=generate_sha256(tokenizer_config_file_name),
                    name=tokenizer_config_file_name,
                    should_show_progress=False,
                    should_verify_checksum=False,
                    required=False,
                )
            )
            
        try:
            self.store.new_snapshot(self.model_tag, snapshot_hash, files)
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError) as e:
            if not self.hf_cli_available:
                perror("URL pull failed and huggingface-cli not available")
                raise KeyError(f"Failed to pull model: {str(e)}")

            model_prefix = ""
            if self.store.model_organization != "":
                    model_prefix = f"{self.store.model_organization}/"

            self.store.prepare_new_snapshot(self.model_tag, snapshot_hash, files)
            for file in files:
                model = model_prefix + file
                conman_args = ["huggingface-cli", "download", "--local-dir", self.store.blob_directory, model]
                if run_cmd(conman_args, debug=debug) != 0 and not file.required:
                    continue
                
                file_hash = generate_sha256(file)
                blob_path = os.path.join(self.store.blob_directory, file_hash)
                os.rename(src=os.path.join(self.store.blob_directory, model), dst=blob_path)

                relative_target_path = os.path.relpath(blob_path, start=self.store.get_snapshot_directory(snapshot_hash))
                os.symlink(relative_target_path, self.store.get_snapshot_file_path(snapshot_hash, file.name))

        return self.store.get_snapshot_file_path(snapshot_hash, model_file_name)

    def push(self, source, args):
        if not self.hf_cli_available:
            raise NotImplementedError(missing_huggingface)
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
