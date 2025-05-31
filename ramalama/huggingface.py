import json
import os
import pathlib
import urllib.request

from ramalama.common import available, perror, run_cmd
from ramalama.logger import logger
from ramalama.model_store import SnapshotFileType
from ramalama.repo_model_base import BaseRepoModel, BaseRepository, RepoFile, fetch_checksum_from_api_base

missing_huggingface = """
Optional: Huggingface models require the huggingface-cli module.
These modules can be installed via PyPi tools like pip, pip3, pipx, or via
distribution package managers like dnf or apt. Example:
pip install huggingface_hub
"""


def is_huggingface_cli_available():
    """Check if huggingface-cli is available on the system."""
    return available("huggingface-cli")


def huggingface_token():
    """Return cached Hugging Face token if it exists otherwise None"""
    token_path = os.path.expanduser(os.path.join("~", ".cache", "huggingface", "token"))
    if os.path.exists(token_path):
        try:
            with open(token_path) as tokenfile:
                return tokenfile.read().strip()
        except OSError:
            pass


def extract_huggingface_checksum(data):
    """Extract SHA-256 checksum from Hugging Face API response."""
    # Extract the SHA-256 checksum from the `oid sha256` line
    for line in data.splitlines():
        if line.startswith("oid sha256:"):
            return line.split(":", 1)[1].strip()
    raise ValueError("SHA-256 checksum not found in the API response.")


def fetch_checksum_from_api(organization, file):
    """Fetch the SHA-256 checksum from the model's metadata API for a given file."""
    checksum_api_url = f"{HuggingfaceRepository.REGISTRY_URL}/{organization}/raw/main/{file}"
    headers = {}
    token = huggingface_token()
    if token is not None:
        headers['Authorization'] = f"Bearer {token}"

    return fetch_checksum_from_api_base(checksum_api_url, headers, extract_huggingface_checksum)


def fetch_repo_manifest(repo_name: str, tag: str = "latest"):
    # Replicate llama.cpp -hf logic
    # https://github.com/ggml-org/llama.cpp/blob/7f323a589f8684c0eb722e7309074cb5eac0c8b5/common/arg.cpp#L611
    token = huggingface_token()
    repo_manifest_url = f"{HuggingfaceRepository.REGISTRY_URL}/v2/{repo_name}/manifests/{tag}"
    logger.debug(f"Fetching repo manifest from {repo_manifest_url}")
    request = urllib.request.Request(
        url=repo_manifest_url,
        headers={
            'User-agent': 'llama-cpp',  # Note: required to return ggufFile field
            'Accept': 'application/json',
        },
    )
    if token is not None:
        request.add_header('Authorization', f"Bearer {token}")

    with urllib.request.urlopen(request) as response:
        repo_manifest = response.read().decode('utf-8')
        return json.loads(repo_manifest)


class HuggingfaceCLIFile(RepoFile):
    pass


class HuggingfaceRepository(BaseRepository):
    REGISTRY_URL = "https://huggingface.co"

    def fetch_metadata(self):
        # Repo org/name. Fetch repo manifest to determine model/mmproj file
        self.blob_url = f"{HuggingfaceRepository.REGISTRY_URL}/{self.organization}/{self.name}/resolve/main"
        self.manifest = fetch_repo_manifest(f"{self.organization}/{self.name}", self.tag)
        try:
            self.model_filename = self.manifest['ggufFile']['rfilename']
            self.model_hash = self.manifest['ggufFile']['blobId']
        except KeyError:
            perror("Repository manifest missing ggufFile data")
            raise
        self.mmproj_filename = self.manifest.get('mmprojFile', {}).get('rfilename', None)
        self.mmproj_hash = self.manifest.get('mmprojFile', {}).get('blobId', None)
        token = huggingface_token()
        if token is not None:
            self.headers['Authorization'] = f"Bearer {token}"


class HuggingfaceRepositoryModel(HuggingfaceRepository):
    def fetch_metadata(self):
        # Model url. organization is <org>/<repo>, name is model file path
        self.blob_url = f"{HuggingfaceRepository.REGISTRY_URL}/{self.organization}/resolve/main"
        self.model_hash = f"sha256:{fetch_checksum_from_api(self.organization, self.name)}"
        self.model_filename = self.name
        token = huggingface_token()
        if token is not None:
            self.headers['Authorization'] = f"Bearer {token}"


def get_repo_info(repo_name):
    # Docs on API call:
    # https://huggingface.co/docs/hub/en/api#get-apimodelsrepoid-or-apimodelsrepoidrevisionrevision
    repo_info_url = f"https://huggingface.co/api/models/{repo_name}"
    logger.debug(f"Fetching repo info from {repo_info_url}")
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


class Huggingface(BaseRepoModel):
    REGISTRY_URL = "https://huggingface.co/v2/"
    ACCEPT = "Accept: application/vnd.docker.distribution.manifest.v2+json"

    def __init__(self, model):
        super().__init__(model)
        self.type = "huggingface"
        self.hf_cli_available = is_huggingface_cli_available()

    def get_cli_command(self):
        return "huggingface-cli"

    def get_missing_message(self):
        return missing_huggingface

    def get_registry_url(self):
        return self.REGISTRY_URL

    def get_accept_header(self):
        return self.ACCEPT

    def get_repo_type(self):
        return "huggingface"

    def fetch_checksum_from_api(self, organization, file):
        return fetch_checksum_from_api(organization, file)

    def create_repository(self, name, organization, tag='latest'):
        return HuggingfaceRepositoryModel(name, organization, tag)

    def get_download_url(self, directory, filename):
        return f"https://huggingface.co/{directory}/resolve/main/{filename}"

    def get_cli_download_args(self, directory_path, model):
        return ["huggingface-cli", "download", "--local-dir", directory_path, model]

    def extract_model_identifiers(self):
        model_name, model_tag, model_organization = super().extract_model_identifiers()
        if '/' not in model_organization:
            # if it is a repo then normalize the case insensitive quantization tag
            if model_tag != "latest":
                model_tag = model_tag.upper()
        return model_name, model_tag, model_organization

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
        return self.cli_pull(args, model_path, directory_path)

    def push(self, _, args):
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
        )
        return proc.stdout.decode("utf-8")

    def _collect_cli_files(self, tempdir: str) -> tuple[str, list[HuggingfaceCLIFile]]:
        cache_dir = os.path.join(tempdir, ".cache", "huggingface", "download")
        files: list[HuggingfaceCLIFile] = []
        snapshot_hash = ""
        for entry in os.listdir(tempdir):
            entry_path = os.path.join(tempdir, entry)
            if os.path.isdir(entry_path) or entry == ".gitattributes":
                continue
            sha256 = ""
            metadata_path = os.path.join(cache_dir, f"{entry}.metadata")
            if not os.path.exists(metadata_path):
                continue
            with open(metadata_path) as metafile:
                lines = metafile.readlines()
                if len(lines) < 2:
                    continue
                sha256 = f"sha256:{lines[1].strip()}"
            if sha256 == "sha256:":
                continue
            if entry.lower() == "readme.md":
                snapshot_hash = sha256
                continue

            hf_file = HuggingfaceCLIFile(
                url=entry_path,
                header={},
                hash=sha256,
                type=SnapshotFileType.Other,
                name=entry,
            )
            # try to identify the model file in the pulled repo
            if entry.endswith(".safetensors") or entry.endswith(".gguf"):
                hf_file.type = SnapshotFileType.Model
            files.append(hf_file)

        return snapshot_hash, files
