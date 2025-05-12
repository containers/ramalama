import json
import os
import pathlib
import tempfile
import urllib.request

from ramalama.common import available, download_and_verify, exec_cmd, perror, run_cmd, verify_checksum
from ramalama.huggingface import HuggingfaceCLIFile, HuggingfaceRepository
from ramalama.model import Model
from ramalama.model_store import SnapshotFileType
from ramalama.ollama_repo_utils import repo_pull

missing_modelscope = """
Optional: ModelScope models require the modelscope module.
These modules can be installed via PyPi tools like pip, pip3, pipx, or via
distribution package managers like dnf or apt. Example:
pip install modelscope
"""


def is_modelscope_available():
    """Check if modelscope is available on the system."""
    return available("modelscope")


def fetch_checksum_from_api(organization, file):
    """Fetch the SHA-256 checksum from the model's metadata API for a given file."""
    checksum_api_url = (
        f"{ModelScopeRepository.REGISTRY_URL}/api/v1/models/{organization}/repo/raw"
        f"?Revision=master&FilePath={file}&Needmeta=true"
    )
    try:
        with urllib.request.urlopen(checksum_api_url) as response:
            data = json.loads(response.read().decode())
        # Extract the SHA-256 checksum from the JSON
        sha256_checksum = data.get("Data", {}).get("MetaContent", {}).get("Sha256")
        if not sha256_checksum:
            raise ValueError("SHA-256 checksum not found in the API response.")
        return sha256_checksum
    except (json.JSONDecodeError, urllib.error.HTTPError, urllib.error.URLError) as e:
        raise KeyError(f"failed to pull {checksum_api_url}: {str(e).strip()}")


class ModelScopeRepository(HuggingfaceRepository):

    REGISTRY_URL = "https://modelscope.cn"

    def __init__(self, name: str, organization: str):
        super().__init__(name, organization)

        self.blob_url = f"{ModelScopeRepository.REGISTRY_URL}/{self.organization}/resolve/master"


class ModelScope(Model):

    REGISTRY_URL = "https://modelscope.cn/"
    ACCEPT = "Accept: application/vnd.docker.distribution.manifest.v2+json"

    def __init__(self, model):
        super().__init__(model)

        self.type = "modelscope"
        self.ms_available = is_modelscope_available()

    def login(self, args):
        if not self.ms_available:
            raise NotImplementedError(missing_modelscope)
        conman_args = ["modelscope", "login"]
        if args.token:
            conman_args.extend(["--token", args.token])
        self.exec(conman_args, args)

    def logout(self, args):
        if not self.ms_available:
            raise NotImplementedError(missing_modelscope)
        conman_args = ["modelscope", "logout"]
        if args.token:
            conman_args.extend(["--token", args.token])
        self.exec(conman_args, args)

    def _attempt_url_pull(self, args, model_path, directory_path):
        try:
            return self.url_pull(args, model_path, directory_path)
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError, ValueError) as e:
            return self._attempt_url_pull_ms(args, model_path, directory_path, e)

    def _attempt_url_pull_ms(self, args, model_path, directory_path, previous_exception):
        if self.ms_available:
            try:
                return self.ms_pull(args, model_path, directory_path)
            except Exception:
                pass
        raise KeyError(f"Failed to pull model: {str(previous_exception)}")

    def pull(self, args):
        if self.store is not None:
            return self._pull_with_model_store(args)

        model_path = self.model_path(args)
        directory_path = os.path.join(args.store, "repos", "modelscope", self.directory, self.filename)
        os.makedirs(directory_path, exist_ok=True)

        symlink_dir = os.path.dirname(model_path)
        os.makedirs(symlink_dir, exist_ok=True)

        # First try to interpret the argument as a user/repo:tag
        try:
            if self.directory.count("/") == 0:

                model_name, model_tag, _ = self.extract_model_identifiers()
                repo_name = self.directory + "/" + model_name
                registry_head = f"{ModelScope.REGISTRY_URL}{repo_name}"

                show_progress = not args.quiet
                return repo_pull(
                    os.path.join(args.store, "repos", "modelscope"),
                    ModelScope.ACCEPT,
                    registry_head,
                    model_name,
                    model_tag,
                    os.path.join(args.store, "models", "modelscope"),
                    model_path,
                    self.model,
                    show_progress,
                )

        except urllib.error.HTTPError:
            if model_tag != "latest":
                # The user explicitly requested a tag, so raise an error
                raise KeyError(f"{self.model} was not found in the ModelScope registry")
            else:
                # The user did not explicitly request a tag, so assume they want the whole repository
                pass

        # Interpreting as a tag did not work.  Attempt to download as a url.
        return self._attempt_url_pull(args, model_path, directory_path)

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
        conman_args = ["modelscope", "download", "--local_dir", directory_path, self.model]
        run_cmd(conman_args, debug=args.debug)

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
        sha256_checksum = fetch_checksum_from_api(self.directory, self.filename)

        target_path = os.path.join(directory_path, f"sha256:{sha256_checksum}")

        if not os.path.exists(target_path):
            self.in_existing_cache(args, target_path, sha256_checksum)

        if os.path.exists(target_path) and verify_checksum(target_path):
            return self._update_symlink(model_path, target_path)

        url = f"https://modelscope.cn/{self.directory}/resolve/master/{self.filename}"
        download_and_verify(url, target_path)
        return self._update_symlink(model_path, target_path)

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
            debug=args.debug,
        )
        return proc.stdout.decode("utf-8")

    def exec(self, cmd_args, args):
        try:
            exec_cmd(cmd_args, debug=args.debug)
        except FileNotFoundError as e:
            print(f"{str(e).strip()}\n{missing_modelscope}")

    def _collect_cli_files(self, tempdir: str) -> tuple[str, list[HuggingfaceCLIFile]]:
        cache_dir = os.path.join(tempdir, ".cache", "modelscope", "download")
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

    def _pull_with_model_store(self, args, debug: bool = False):
        name, tag, organization = self.extract_model_identifiers()
        hash, cached_files, all = self.store.get_cached_files(tag)
        if all:
            if not args.quiet:
                print(f"Using cached modelscope://{name}:{tag} ...")
            return self.store.get_snapshot_file_path(hash, name)

        try:
            # Fetch the SHA-256 checksum of model from the API and use as snapshot hash
            snapshot_hash = f"sha256:{fetch_checksum_from_api(organization, name)}"
            if not args.quiet:
                self.print_pull_message(f"ms://{name}:{tag}")

            ms_repo = ModelScopeRepository(name, organization)
            files = ms_repo.get_file_list(cached_files, snapshot_hash)
            self.store.new_snapshot(tag, snapshot_hash, files)
        except Exception as e:
            if not self.ms_available:
                perror("URL pull failed and modelscope not available")
                raise KeyError(f"Failed to pull model: {str(e)}")

            # Cleanup previously created snapshot
            try:
                self.store.remove_snapshot(tag)
            except Exception:
                # ignore any error when removing snapshot
                pass

            # Create temporary directory for downloading via modelscope
            with tempfile.TemporaryDirectory() as tempdir:
                model = f"{organization}/{name}"
                conman_args = ["modelscope", "download", "--local_dir", tempdir, model]
                run_cmd(conman_args, debug=debug)

                snapshot_hash, files = self._collect_cli_files(tempdir)
                self.store.new_snapshot(tag, snapshot_hash, files)

        return self.store.get_snapshot_file_path(snapshot_hash, self.store.model_name)
