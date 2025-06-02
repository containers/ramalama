import json
import os
import pathlib
import tempfile
import urllib.request
from abc import ABC, abstractmethod

from ramalama.common import available, download_and_verify, exec_cmd, generate_sha256, perror, run_cmd, verify_checksum
from ramalama.logger import logger
from ramalama.model import Model
from ramalama.model_store import SnapshotFile, SnapshotFileType
from ramalama.ollama_repo_utils import repo_pull


class RepoFile(SnapshotFile):
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


class BaseRepository(ABC):
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


class BaseRepoModel(Model, ABC):
    def __init__(self, model):
        super().__init__(model)

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
    def create_repository(self, name, organization, tag='latest'):
        """Create repository instance"""
        pass

    @abstractmethod
    def get_download_url(self, directory, filename):
        """Get download URL for file"""
        pass

    @abstractmethod
    def get_cli_download_args(self, directory_path, model):
        """Get CLI download arguments"""
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

    def _attempt_url_pull(self, args, model_path, directory_path):
        try:
            return self.url_pull(args, model_path, directory_path)
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError, ValueError) as e:
            return self._attempt_url_pull_cli(args, model_path, directory_path, e)

    def _attempt_url_pull_cli(self, args, model_path, directory_path, previous_exception):
        if available(self.get_cli_command()):
            try:
                return self.cli_pull(args, model_path, directory_path)
            except Exception as exc:
                logger.debug(f"failed to cli_pull: {exc}")
                pass
        raise KeyError(f"Failed to pull model: {str(previous_exception)}")

    def pull(self, args):
        if self.store is not None:
            return self._pull_with_model_store(args)

        model_path = self.model_path(args)
        directory_path = os.path.join(args.store, "repos", self.get_repo_type(), self.directory, self.filename)
        os.makedirs(directory_path, exist_ok=True)

        symlink_dir = os.path.dirname(model_path)
        os.makedirs(symlink_dir, exist_ok=True)

        # First try to interpret the argument as a user/repo:tag
        try:
            if self.directory.count("/") == 0:
                model_name, model_tag, _ = self.extract_model_identifiers()
                repo_name = f"{self.directory}/{model_name}"
                registry_head = f"{self.get_registry_url()}{repo_name}"

                show_progress = not args.quiet
                return repo_pull(
                    os.path.join(args.store, "repos", self.get_repo_type()),
                    self.get_accept_header(),
                    registry_head,
                    model_name,
                    model_tag,
                    os.path.join(args.store, "models", self.get_repo_type()),
                    model_path,
                    self.model,
                    show_progress,
                )

        except urllib.error.HTTPError:
            if model_tag != "latest":
                # The user explicitly requested a tag, so raise an error
                raise KeyError(f"{self.model} was not found in the {self.get_repo_type()} registry")
            else:
                # The user did not explicitly request a tag, so assume they want the whole repository
                pass

        # Interpreting as a tag did not work.  Attempt to download as a url.
        return self._attempt_url_pull(args, model_path, directory_path)

    def cli_pull(self, args, model_path, directory_path):
        conman_args = self.get_cli_download_args(directory_path, self.model)
        run_cmd(conman_args)

        relative_target_path = os.path.relpath(directory_path, start=os.path.dirname(model_path))
        pathlib.Path(model_path).unlink(missing_ok=True)
        os.symlink(relative_target_path, model_path)
        return model_path

    def _update_symlink(self, model_path, target_path):
        relative_target_path = os.path.relpath(target_path, start=os.path.dirname(model_path))
        if not self.check_valid_model_path(relative_target_path, model_path):
            pathlib.Path(model_path).unlink(missing_ok=True)
            os.symlink(relative_target_path, model_path)
        return model_path

    def url_pull(self, args, model_path, directory_path):
        # Fetch the SHA-256 checksum from the API
        sha256_checksum = self.fetch_checksum_from_api(self.directory, self.filename)

        target_path = os.path.join(directory_path, f"sha256:{sha256_checksum}")

        if not os.path.exists(target_path):
            self.in_existing_cache(args, target_path, sha256_checksum)

        if os.path.exists(target_path) and verify_checksum(target_path):
            return self._update_symlink(model_path, target_path)

        # Download the model file to the target path
        url = self.get_download_url(self.directory, self.filename)
        download_and_verify(url, target_path)
        return self._update_symlink(model_path, target_path)

    def exec(self, cmd_args, args):
        try:
            exec_cmd(cmd_args)
        except FileNotFoundError as e:
            print(f"{str(e).strip()}\n{self.get_missing_message()}")

    @abstractmethod
    def in_existing_cache(self, args, target_path, sha256_checksum):
        """Check if file exists in existing cache"""
        pass

    @abstractmethod
    def _collect_cli_files(self, tempdir: str):
        """Collect files from CLI download"""
        pass

    def _pull_with_model_store(self, args):
        name, tag, organization = self.extract_model_identifiers()
        hash, cached_files, all = self.store.get_cached_files(tag)
        if all:
            if not args.quiet:
                print(f"Using cached {self.get_repo_type()}://{name}:{tag} ...")
            return self.store.get_snapshot_file_path(hash, name)

        try:
            if not args.quiet:
                self.print_pull_message(f"{self.get_repo_type()}://{name}:{tag}")

            repo = self.create_repository(name, organization)
            snapshot_hash = repo.model_hash
            files = repo.get_file_list(cached_files)
            self.store.new_snapshot(tag, snapshot_hash, files)

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
                self.store.new_snapshot(tag, snapshot_hash, files)

        return self.store.get_snapshot_file_path(snapshot_hash, self.store.get_ref_file(tag).model_name)
