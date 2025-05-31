import json
import os

from ramalama.common import available, run_cmd
from ramalama.model_store import SnapshotFileType
from ramalama.repo_model_base import BaseRepoModel, BaseRepository, RepoFile, fetch_checksum_from_api_base

missing_modelscope = """
Optional: ModelScope models require the modelscope module.
These modules can be installed via PyPi tools like pip, pip3, pipx, or via
distribution package managers like dnf or apt. Example:
pip install modelscope
"""


def is_modelscope_available():
    """Check if modelscope is available on the system."""
    return available("modelscope")


def extract_modelscope_checksum(data):
    """Extract SHA-256 checksum from ModelScope API response."""
    parsed_data = json.loads(data)
    if sha256_checksum := parsed_data.get("Data", {}).get("MetaContent", {}).get("Sha256"):
        return sha256_checksum
    else:
        raise ValueError("SHA-256 checksum not found in the API response.")


def fetch_checksum_from_api(organization, file):
    """Fetch the SHA-256 checksum from the model's metadata API for a given file."""
    checksum_api_url = (
        f"{ModelScopeRepository.REGISTRY_URL}/api/v1/models/{organization}/repo/raw"
        f"?Revision=master&FilePath={file}&Needmeta=true"
    )

    return fetch_checksum_from_api_base(checksum_api_url, None, extract_modelscope_checksum)


class ModelScopeRepository(BaseRepository):

    REGISTRY_URL = "https://modelscope.cn"

    def fetch_metadata(self):
        self.blob_url = f"{ModelScopeRepository.REGISTRY_URL}/{self.organization}/resolve/master"
        self.model_hash = f"sha256:{fetch_checksum_from_api(self.organization, self.name)}"
        self.model_filename = self.name


class ModelScope(BaseRepoModel):

    REGISTRY_URL = "https://modelscope.cn/"
    ACCEPT = "Accept: application/vnd.docker.distribution.manifest.v2+json"

    def __init__(self, model):
        super().__init__(model)
        self.type = "modelscope"
        self.ms_available = is_modelscope_available()

    def get_cli_command(self):
        return "modelscope"

    def get_missing_message(self):
        return missing_modelscope

    def get_registry_url(self):
        return self.REGISTRY_URL

    def get_accept_header(self):
        return self.ACCEPT

    def get_repo_type(self):
        return "modelscope"

    def fetch_checksum_from_api(self, organization, file):
        return fetch_checksum_from_api(organization, file)

    def create_repository(self, name, organization, tag='latest'):
        return ModelScopeRepository(name, organization, tag)

    def get_download_url(self, directory, filename):
        return f"https://modelscope.cn/{directory}/resolve/master/{filename}"

    def get_cli_download_args(self, directory_path, model):
        return ["modelscope", "download", "--local_dir", directory_path, model]

    def _fetch_cache_path(self, cache_dir, namespace, repo):
        def normalize_repo_name(repo):
            return repo.replace(".", "___")

        return os.path.join(cache_dir, 'models', namespace, normalize_repo_name(repo))

    def in_existing_cache(self, args, target_path, sha256_checksum):
        if not self.ms_available:
            return False

        default_ms_caches = [os.path.join(os.environ['HOME'], '.cache/modelscope/hub')]
        namespace, repo = os.path.split(str(self.directory))

        for cache_dir in default_ms_caches:
            cache_path = self._fetch_cache_path(cache_dir, namespace, repo)
            if not cache_path or not os.path.exists(cache_path):
                continue

            file_path = os.path.join(cache_path, self.filename)
            if not os.path.exists(file_path):
                continue

            os.symlink(file_path, target_path)
            return True
        return False

    def ms_pull(self, args, model_path, directory_path):
        return self.cli_pull(args, model_path, directory_path)

    def push(self, _, args):
        if not self.ms_available:
            raise NotImplementedError(missing_modelscope)
        proc = run_cmd(
            [
                "modelscope",
                "upload",
                "--repo-type",
                "model",
                self.directory,
                self.filename,
                "--cache_dir",
                os.path.join(args.store, "repos", "modelscope", ".cache"),
                "--local_dir",
                os.path.join(args.store, "repos", "modelscope", self.directory),
            ],
        )
        return proc.stdout.decode("utf-8")

    def _collect_cli_files(self, tempdir: str) -> tuple[str, list[RepoFile]]:
        cache_dir = os.path.join(tempdir, ".cache", "modelscope", "download")
        files: list[RepoFile] = []
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

            ms_file = RepoFile(
                url=entry_path,
                header={},
                hash=sha256,
                type=SnapshotFileType.Other,
                name=entry,
            )
            # try to identify the model file in the pulled repo
            if entry.endswith(".safetensors") or entry.endswith(".gguf"):
                ms_file.type = SnapshotFileType.Model
            files.append(ms_file)

        return snapshot_hash, files
