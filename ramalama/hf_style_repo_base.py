import json
import os
import tempfile
import urllib.request
from abc import ABC, abstractmethod

from ramalama.common import available, exec_cmd, generate_sha256, perror, run_cmd
from ramalama.logger import logger
from ramalama.model import Model
from ramalama.model_store.snapshot_file import SnapshotFile, SnapshotFileType


class HFStyleRepoFile(SnapshotFile):
    def __init__(
        self, url, header, hash, name, type, should_show_progress=False, should_verify_checksum=False, required=True
    ):
        super().__init__(url, header, hash, name, type, should_show_progress, should_verify_checksum, required)

    def download(self, blob_file_path, snapshot_dir):
        # moving from the cached temp directory to blob directory
        import shutil

        shutil.move(self.url, blob_file_path)
        return os.path.relpath(blob_file_path, start=snapshot_dir)


def fetch_checksum_from_api_base(checksum_api_url, headers=None, extractor_func=None):
    """
    Base function for fetching checksums from API endpoints.

    Args:
    checksum_api_url (str): The URL of the API endpoint to fetch the checksum from.
    headers (dict, optional): Optional headers to include in the request.
    extractor_func (callable, optional): Optional function to extract the checksum from the response data.

    Returns:
    str: The extracted checksum or the raw response data.

    Raises:
    KeyError: If the API request fails or the checksum cannot be extracted.
    """
    logger.debug(f"Fetching checksum from {checksum_api_url}")
    request = urllib.request.Request(url=checksum_api_url)
    if headers:
        for key, value in headers.items():
            request.add_header(key, value)

    try:
        with urllib.request.urlopen(request) as response:
            data = response.read().decode()

        return extractor_func(data) if extractor_func else data.strip()

    except (json.JSONDecodeError, urllib.error.HTTPError, urllib.error.URLError) as e:
        raise KeyError(f"failed to pull {checksum_api_url}: {str(e).strip()}")


class HFStyleRepository(ABC):
    FILE_NAME_CONFIG = "config.json"
    FILE_NAME_GENERATION_CONFIG = "generation_config.json"
    FILE_NAME_TOKENIZER_CONFIG = "tokenizer_config.json"

    def __init__(self, name: str, organization: str, tag: str = 'latest'):
        self.name = name
        self.organization = organization
        self.tag = tag
        self.headers = {}
        self.blob_url = None
        self.model_filename = None
        self.model_hash = None
        self.mmproj_filename = None
        self.mmproj_hash = None
        self.fetch_metadata()

    @abstractmethod
    def fetch_metadata(self):
        pass

    def get_file_list(self, cached_files: list[str]) -> list[SnapshotFile]:
        files = []
        if self.model_filename not in cached_files:
            files.append(self.model_file())
        if self.mmproj_filename and self.mmproj_filename not in cached_files:
            files.append(self.mmproj_file())
        if self.FILE_NAME_CONFIG not in cached_files:
            files.append(self.config_file())
        if self.FILE_NAME_GENERATION_CONFIG not in cached_files:
            files.append(self.generation_config_file())
        if self.FILE_NAME_TOKENIZER_CONFIG not in cached_files:
            files.append(self.tokenizer_config_file())

        return files

    def model_file(self) -> SnapshotFile:
        return SnapshotFile(
            url=f"{self.blob_url}/{self.model_filename}",
            header=self.headers,
            hash=self.model_hash,
            type=SnapshotFileType.Model,
            name=self.model_filename,
            should_show_progress=True,
            should_verify_checksum=True,
        )

    def mmproj_file(self) -> SnapshotFile:
        return SnapshotFile(
            url=f"{self.blob_url}/{self.mmproj_filename}",
            header=self.headers,
            hash=self.mmproj_hash,
            type=SnapshotFileType.Mmproj,
            name=self.mmproj_filename,
            required=False,
            should_show_progress=True,
            should_verify_checksum=True,
        )

    def config_file(self) -> SnapshotFile:
        return SnapshotFile(
            url=f"{self.blob_url}/{self.FILE_NAME_CONFIG}",
            header=self.headers,
            hash=generate_sha256(self.FILE_NAME_CONFIG),
            type=SnapshotFileType.Other,
            name=self.FILE_NAME_CONFIG,
            required=False,
        )

    def generation_config_file(self) -> SnapshotFile:
        return SnapshotFile(
            url=f"{self.blob_url}/{self.FILE_NAME_GENERATION_CONFIG}",
            header=self.headers,
            hash=generate_sha256(self.FILE_NAME_GENERATION_CONFIG),
            type=SnapshotFileType.Other,
            name=self.FILE_NAME_GENERATION_CONFIG,
            required=False,
        )

    def tokenizer_config_file(self) -> SnapshotFile:
        return SnapshotFile(
            url=f"{self.blob_url}/{self.FILE_NAME_TOKENIZER_CONFIG}",
            header=self.headers,
            hash=generate_sha256(self.FILE_NAME_TOKENIZER_CONFIG),
            type=SnapshotFileType.Other,
            name=self.FILE_NAME_TOKENIZER_CONFIG,
            required=False,
        )


class HFStyleRepoModel(Model, ABC):
    def __init__(self, model, model_store_path):
        super().__init__(model, model_store_path)

    @abstractmethod
    def get_cli_command(self):
        """Return the CLI command name (e.g., 'huggingface-cli', 'modelscope')"""
        pass

    @abstractmethod
    def get_missing_message(self):
        """Return the missing CLI message"""
        pass

    @abstractmethod
    def get_registry_url(self):
        """Return the registry URL"""
        pass

    @abstractmethod
    def get_accept_header(self):
        """Return the accept header"""
        pass

    @abstractmethod
    def get_repo_type(self):
        """Return the repo type name (e.g., 'huggingface', 'modelscope')"""
        pass

    @abstractmethod
    def fetch_checksum_from_api(self, organization, file):
        """Fetch checksum from API"""
        pass

    @abstractmethod
    def create_repository(self, name, organization, tag):
        """Create repository instance"""
        pass

    @abstractmethod
    def get_cli_download_args(self, directory_path, model):
        """Get CLI download arguments"""
        pass

    @abstractmethod
    def in_existing_cache(self, args, target_path, sha256_checksum):
        """Check if file exists in existing cache"""
        pass

    @abstractmethod
    def _collect_cli_files(self, tempdir: str):
        """Collect files from CLI download"""
        pass

    def login(self, args):
        if not available(self.get_cli_command()):
            raise NotImplementedError(self.get_missing_message())
        conman_args = [self.get_cli_command(), "login"]
        if args.token:
            conman_args.extend(["--token", args.token])
        self.exec(conman_args, args)

    def logout(self, args):
        if not available(self.get_cli_command()):
            raise NotImplementedError(self.get_missing_message())
        conman_args = [self.get_cli_command(), "logout"]
        if args.token:
            conman_args.extend(["--token", args.token])
        self.exec(conman_args, args)

    def pull(self, args):
        name, tag, organization = self.extract_model_identifiers()
        _, cached_files, all = self.model_store.get_cached_files(tag)
        if all:
            if not args.quiet:
                perror(f"Using cached {self.get_repo_type()}://{name}:{tag} ...")
            return

        try:
            if not args.quiet:
                self.print_pull_message(f"{self.get_repo_type()}://{organization}/{name}:{tag}")

            repo = self.create_repository(name, organization, tag)
            snapshot_hash = repo.model_hash
            files = repo.get_file_list(cached_files)
            self.model_store.new_snapshot(tag, snapshot_hash, files)

        except Exception as e:
            if not available(self.get_cli_command()):
                perror(f"URL pull failed and {self.get_cli_command()} not available")
                raise KeyError(f"Failed to pull model: {str(e)}")

            # Create temporary directory for downloading via CLI
            with tempfile.TemporaryDirectory() as tempdir:
                model = f"{organization}/{name}"
                conman_args = self.get_cli_download_args(tempdir, model)
                run_cmd(conman_args)

                snapshot_hash, files = self._collect_cli_files(tempdir)
                self.model_store.new_snapshot(tag, snapshot_hash, files)

    def exec(self, cmd_args, args):
        try:
            exec_cmd(cmd_args)
        except FileNotFoundError as e:
            perror(f"{str(e).strip()}\n{self.get_missing_message()}")
