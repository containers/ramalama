import json
import os
import pathlib
import shutil
import tempfile
import urllib.request

from ramalama.common import available, download_file, exec_cmd, generate_sha256, perror, run_cmd, verify_checksum
from ramalama.model import Model
from ramalama.model_store import SnapshotFile, SnapshotFileType

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
    """Fetch the SHA-256 checksum from the model's metadata API for a given file."""
    checksum_api_url = f"{HuggingfaceRepository.REGISTRY_URL}/{organization}/raw/main/{file}"
    try:
        with urllib.request.urlopen(checksum_api_url) as response:
            data = response.read().decode()
        # Extract the SHA-256 checksum from the `oid sha256` line
        for line in data.splitlines():
            if line.startswith("oid sha256:"):
                return line.split(":", 1)[1].strip()
        raise ValueError("SHA-256 checksum not found in the API response.")
    except urllib.error.HTTPError as e:
        raise KeyError(f"failed to pull {checksum_api_url}: " + str(e).strip("'"))
    except urllib.error.URLError as e:
        raise KeyError(f"failed to pull {checksum_api_url}: " + str(e).strip("'"))


class HuggingfaceCLIFile(SnapshotFile):

    def __init__(
        self, url, header, hash, name, type, should_show_progress=False, should_verify_checksum=False, required=True
    ):
        super().__init__(url, header, hash, name, type, should_show_progress, should_verify_checksum, required)

    def download(self, blob_file_path, snapshot_dir):
        # moving from the cached temp directory to blob directory
        shutil.move(self.url, blob_file_path)
        return os.path.relpath(blob_file_path, start=snapshot_dir)


class HuggingfaceRepository:

    REGISTRY_URL = "https://huggingface.co"

    FILE_NAME_CONFIG = "config.json"
    FILE_NAME_GENERATION_CONFIG = "generation_config.json"
    FILE_NAME_TOKENIZER_CONFIG = "tokenizer_config.json"

    def __init__(self, name: str, organization: str):
        self.name = name
        self.organization = organization

        self.blob_url = f"{HuggingfaceRepository.REGISTRY_URL}/{self.organization}/resolve/main"
        self.headers = {}

    def get_file_list(self, cached_files: list[str], snapshot_hash: str) -> list[SnapshotFile]:
        files = []
        if self.name not in cached_files:
            files.append(self.model_file(snapshot_hash))
        if HuggingfaceRepository.FILE_NAME_CONFIG not in cached_files:
            files.append(self.config_file())
        if HuggingfaceRepository.FILE_NAME_GENERATION_CONFIG not in cached_files:
            files.append(self.generation_config_file())
        if HuggingfaceRepository.FILE_NAME_TOKENIZER_CONFIG not in cached_files:
            files.append(self.tokenizer_config_file())

        return files

    def model_file(self, snapshot_hash: str) -> SnapshotFile:
        return SnapshotFile(
            url=f"{self.blob_url}/{self.name}",
            header=self.headers,
            hash=snapshot_hash,
            type=SnapshotFileType.Model,
            name=self.name,
            should_show_progress=True,
            should_verify_checksum=True,
        )

    def config_file(self) -> SnapshotFile:
        return SnapshotFile(
            url=f"{self.blob_url}/{HuggingfaceRepository.FILE_NAME_CONFIG}",
            header=self.headers,
            hash=generate_sha256(HuggingfaceRepository.FILE_NAME_CONFIG),
            type=SnapshotFileType.Other,
            name=HuggingfaceRepository.FILE_NAME_CONFIG,
            required=False,
        )

    def generation_config_file(self) -> SnapshotFile:
        return SnapshotFile(
            url=f"{self.blob_url}/{HuggingfaceRepository.FILE_NAME_GENERATION_CONFIG}",
            header=self.headers,
            hash=generate_sha256(HuggingfaceRepository.FILE_NAME_GENERATION_CONFIG),
            type=SnapshotFileType.Other,
            name=HuggingfaceRepository.FILE_NAME_GENERATION_CONFIG,
            required=False,
        )

    def tokenizer_config_file(self) -> SnapshotFile:
        return SnapshotFile(
            url=f"{self.blob_url}/{HuggingfaceRepository.FILE_NAME_TOKENIZER_CONFIG}",
            header=self.headers,
            hash=generate_sha256(HuggingfaceRepository.FILE_NAME_TOKENIZER_CONFIG),
            type=SnapshotFileType.Other,
            name=HuggingfaceRepository.FILE_NAME_TOKENIZER_CONFIG,
            required=False,
        )


def get_repo_info(repo_name):
    # Docs on API call:
    # https://huggingface.co/docs/hub/en/api#get-apimodelsrepoid-or-apimodelsrepoidrevisionrevision
    repo_info_url = f"https://huggingface.co/api/models/{repo_name}"
    with urllib.request.urlopen(repo_info_url) as response:
        if response.getcode() == 200:
            repo_info = response.read().decode('utf-8')
            return json.loads(repo_info)
        else:
            perror("Huggingface repo information pull failed")
            raise KeyError(f"Response error code from repo info pull: {response.getcode()}")
    return None


def handle_repo_info(repo_name, repo_info, runtime):
    if "safetensors" in repo_info and runtime == "llama.cpp":
        print(
            "\nllama.cpp does not support running safetensor models, "
            "please use a/convert to the GGUF format using:\n"
            f"- https://huggingface.co/models?other=base_model:quantized:{repo_name} \n"
            "- https://huggingface.co/spaces/ggml-org/gguf-my-repo"
        )
    if "gguf" in repo_info:
        print("There are GGUF files to choose from in this repo, use one of the following commands to run one:\n")
    for sibling in repo_info.get("siblings", []):
        if sibling["rfilename"].endswith('.gguf'):
            file = sibling["rfilename"]
            print(f"- ramalama run hf://{repo_name}/{file}")
    print("\n")


class Huggingface(Model):
    def __init__(self, model):
        super().__init__(model)

        self.type = "huggingface"
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

    def pull(self, args):
        if self.store is not None:
            return self._pull_with_model_store()

        model_path = self.model_path(args)
        directory_path = os.path.join(args.store, "repos", "huggingface", self.directory, self.filename)
        os.makedirs(directory_path, exist_ok=True)

        symlink_dir = os.path.dirname(model_path)
        os.makedirs(symlink_dir, exist_ok=True)

        try:
            # Check if huggingface repo instead of file
            if self.directory.count("/") == 0:
                repo_name = self.directory + "/" + self.filename
                repo_info = get_repo_info(repo_name)
                handle_repo_info(repo_name, repo_info, args.runtime)

            return self.url_pull(args, model_path, directory_path)
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError) as e:
            if self.hf_cli_available:
                return self.hf_pull(args, model_path, directory_path)
            perror("URL pull failed and huggingface-cli not available")
            raise KeyError(f"Failed to pull model: {str(e)}")

    def _fetch_snapshot_path(self, cache_dir, namespace, repo):
        cache_path = os.path.join(cache_dir, f'models--{namespace}--{repo}')
        main_ref_path = os.path.join(cache_path, 'refs', 'main')
        if not (os.path.exists(cache_path) and os.path.exists(main_ref_path)):
            return None, None
        with open(main_ref_path, 'r') as file:
            snapshot = file.read().strip()
        snapshot_path = os.path.join(cache_path, 'snapshots', snapshot)
        return snapshot_path, cache_path

    def in_existing_cache(self, args, target_path, sha256_checksum):
        if not self.hf_cli_available:
            return False

        default_hf_caches = [os.path.join(os.environ['HOME'], '.cache/huggingface/hub')]
        namespace, repo = os.path.split(str(self.directory))

        for cache_dir in default_hf_caches:
            snapshot_path, cache_path = self._fetch_snapshot_path(cache_dir, namespace, repo)
            if not snapshot_path or not os.path.exists(snapshot_path):
                continue

            file_path = os.path.join(snapshot_path, self.filename)
            if not os.path.exists(file_path):
                continue

            blob_path = pathlib.Path(file_path).resolve()
            if not os.path.exists(blob_path):
                continue

            blob_file = os.path.relpath(blob_path, start=os.path.join(cache_path, 'blobs'))
            if str(blob_file) != str(sha256_checksum):
                continue

            os.symlink(blob_path, target_path)
            return True
        return False

    def hf_pull(self, args, model_path, directory_path):
        conman_args = ["huggingface-cli", "download", "--local-dir", directory_path, self.model]
        run_cmd(conman_args, debug=args.debug)

        relative_target_path = os.path.relpath(directory_path, start=os.path.dirname(model_path))
        pathlib.Path(model_path).unlink(missing_ok=True)
        os.symlink(relative_target_path, model_path)
        return model_path

    def url_pull(self, args, model_path, directory_path):
        # Fetch the SHA-256 checksum from the API
        sha256_checksum = fetch_checksum_from_api(self.directory, self.filename)

        target_path = os.path.join(directory_path, f"sha256:{sha256_checksum}")

        if not os.path.exists(target_path):
            self.in_existing_cache(args, target_path, sha256_checksum)

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

    def _collect_cli_files(self, tempdir: str) -> tuple[str, list[HuggingfaceCLIFile]]:
        cache_dir = os.path.join(tempdir, ".cache", "huggingface", "download")
        files: list[HuggingfaceCLIFile] = []
        snapshot_hash = ""
        for entry in os.listdir(tempdir):
            entry_path = os.path.join(tempdir, entry)
            if os.path.isdir(entry_path) or entry == ".gitattributes":
                continue
            sha256 = ""
            with open(os.path.join(cache_dir, f"{entry}.metadata")) as metafile:
                metafile.readline()
                sha256 = f"sha256:{metafile.readline().strip()}"
            if sha256 == "sha256:":
                continue
            if entry.lower() == "readme.md":
                snapshot_hash = sha256
                continue
            files.append(
                HuggingfaceCLIFile(
                    url=entry_path,
                    header={},
                    hash=sha256,
                    type=SnapshotFileType.Other,
                    name=entry,
                )
            )

        return snapshot_hash, files

    def _pull_with_model_store(self, debug: bool = False):
        name, tag, organization = self.extract_model_identifiers()
        hash, cached_files, all = self.store.get_cached_files(tag)
        if all:
            return self.store.get_snapshot_file_path(hash, name)

        try:
            # Fetch the SHA-256 checksum of model from the API and use as snapshot hash
            snapshot_hash = f"sha256:{fetch_checksum_from_api(self.organization, self.name)}"

            hf_repo = HuggingfaceRepository(name, organization)
            files = hf_repo.get_file_list(cached_files, snapshot_hash)
            self.store.new_snapshot(tag, snapshot_hash, files)
        except Exception as e:
            if not self.hf_cli_available:
                perror("URL pull failed and huggingface-cli not available")
                raise KeyError(f"Failed to pull model: {str(e)}")

            # Cleanup previously created snapshot
            self.store.remove_snapshot(tag)

            # Create temporary directory for downloading via huggingface-cli
            with tempfile.TemporaryDirectory() as tempdir:
                model = f"{organization}/{name}"
                conman_args = ["huggingface-cli", "download", "--local-dir", tempdir, model]
                run_cmd(conman_args, debug=debug)

                snapshot_hash, files = self._collect_cli_files(tempdir)
                self.store.new_snapshot(tag, snapshot_hash, files)

        return self.store.get_snapshot_file_path(snapshot_hash, self.store.model_name)
