import json
import os
import urllib.request
from pathlib import Path

from ramalama.common import run_cmd
from ramalama.hf_style_repo_base import (
    HFStyleRepoFile,
    HFStyleRepoModel,
    HFStyleRepository,
    fetch_checksum_from_api_base,
)
from ramalama.logger import logger

missing_huggingface = """This operation requires huggingface-cli which is not available.

This tool can be installed via PyPI tools like uv, pip, pip3 or pipx. Example:

pip install -U "huggingface_hub[cli]"

Or via distribution package managers like dnf or apt. Example:

sudo dnf install python3-huggingface-hub
"""


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


def fetch_repo_files(repo_name: str, revision: str = "main"):
    """Fetch the list of files in a HuggingFace repository using the Files API with pagination support."""
    token = huggingface_token()
    base_api_url = f"https://huggingface.co/api/models/{repo_name}/tree/{revision}"

    all_files = []
    next_url: str | None = base_api_url

    # TODO: Handle Diffusers-multifolder layout
    # See https://huggingface.co/docs/diffusers/v0.35.1/using-diffusers/other-formats#diffusers-multifolder
    while next_url:
        logger.debug(f"Fetching repo files from {next_url}")

        request = urllib.request.Request(
            url=next_url,
            headers={
                'Accept': 'application/json',
            },
        )
        if token is not None:
            request.add_header('Authorization', f"Bearer {token}")

        with urllib.request.urlopen(request) as response:
            files_data = response.read().decode('utf-8')
            data = json.loads(files_data)

            # Response should be a list of files or a dict
            if isinstance(data, list):
                all_files.extend(data)
            elif isinstance(data, dict):
                files = data.get('files') or data.get('siblings') or []
                all_files.extend(files)
            else:
                raise ValueError(f"Unexpected response from HuggingFace API: {type(data)}")

            # Check for pagination via Link header
            next_url = None
            link_header = response.headers.get('Link')
            if link_header:
                # Parse Link header: <url>; rel="next"
                # Example: '<https://huggingface.co/api/models/foo/tree/main?cursor=abc>; rel="next"'
                for link in link_header.split(','):
                    parts = link.split(';')
                    has_next_rel = any('rel="next"' in p.strip() or "rel='next'" in p.strip() for p in parts)
                    if has_next_rel:
                        for p in parts:
                            p = p.strip()
                            if p.startswith('<') and p.endswith('>'):
                                next_url = p[1:-1]
                                logger.debug(f"Found next page via Link header: {next_url}")
                                break
                        if next_url:
                            break

    logger.debug(f"Fetched {len(all_files)} total files from repository {repo_name}")
    return all_files


class HuggingfaceCLIFile(HFStyleRepoFile):
    pass


class HuggingfaceRepository(HFStyleRepository):
    REGISTRY_URL = "https://huggingface.co"

    def _fetch_manifest_metadata(self):
        # Repo org/name. Fetch repo manifest to determine model/mmproj file
        self.blob_url = f"{HuggingfaceRepository.REGISTRY_URL}/{self.organization}/{self.name}/resolve/main"

        try:
            self.manifest = fetch_repo_manifest(f"{self.organization}/{self.name}", self.tag)
        except (urllib.error.HTTPError, json.JSONDecodeError, KeyError) as e:
            logger.debug(f'fetch_repo_manifest failed: {e}')
            return False
        try:
            # Note that the blobId in the manifest already has a sha256: prefix
            self.model_filename = self.manifest['ggufFile']['rfilename']
            self.model_hash = self.manifest['ggufFile']['blobId']
            self.mmproj_filename = self.manifest.get('mmprojFile', {}).get('rfilename', None)
            self.mmproj_hash = self.manifest.get('mmprojFile', {}).get('blobId', None)
            return True
        except KeyError:
            # No ggufFile in manifest
            return False

    def _collect_file(self, file_list, file_info):
        path = file_info['path']
        oid = file_info.get('oid', '')
        if 'lfs' in file_info and 'oid' in file_info['lfs']:
            oid = file_info['lfs']['oid']
        file_list.append({'filename': path, 'oid': oid})

    def _fetch_safetensors_metadata(self):
        """Fetch metadata for safetensors models from HuggingFace API."""
        repo_name = f"{self.organization}/{self.name}"
        try:
            files = fetch_repo_files(repo_name)
        except (urllib.error.HTTPError, json.JSONDecodeError, KeyError) as e:
            logger.debug(f'fetch_repo_files failed: {e}')
            return False

        # Find all safetensors files, config files and index files
        safetensors_files = []
        self.other_files = []
        index_file = None

        try:
            for file_info in files:
                if file_info.get('type') != 'file':
                    continue

                path_str = file_info['path']
                logger.debug(f"Examining file {path_str}")

                path = Path(path_str)
                # Note: case sensitivity follows platform defaults
                if path.match('*.safetensors'):
                    self._collect_file(safetensors_files, file_info)
                elif path.match('*.safetensors.index.json'):
                    index_file = path_str
                elif path_str in {
                    self.FILE_NAME_CONFIG,
                    self.FILE_NAME_GENERATION_CONFIG,
                    self.FILE_NAME_TOKENIZER_CONFIG,
                }:
                    continue
                else:
                    self._collect_file(self.other_files, file_info)

            if not safetensors_files:
                logger.debug('No safetensors files found')
                return False

            # Sort safetensors files by name for consistent ordering
            safetensors_files.sort(key=lambda x: x['filename'])

            # Use the first safetensors file as the main model
            # If there are multiple files, they might be sharded
            self.model_filename = safetensors_files[0]['filename']
            self.model_hash = f"sha256:{safetensors_files[0]['oid']}"

            # Store additional safetensors files for get_file_list
            self.additional_safetensor_files = safetensors_files[1:]

            # Store index file if found
            self.safetensors_index_file = index_file
        except (KeyError, ValueError) as e:
            logger.debug(f'_fetch_safetensors_metadata failed: {e}')
            return False

        return True

    def fetch_metadata(self):
        # Try to fetch GGUF manifest first, then safetensors metadata
        if not self._fetch_manifest_metadata() and not self._fetch_safetensors_metadata():
            raise KeyError("No metadata found")

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


class Huggingface(HFStyleRepoModel):
    REGISTRY_URL = "https://huggingface.co/v2/"
    ACCEPT = "Accept: application/vnd.docker.distribution.manifest.v2+json"

    def __init__(self, model, model_store_path):
        super().__init__(model, model_store_path)

        self.type = "huggingface"

    def get_cli_command(self):
        return "hf"

    def get_login_args(self):
        """HuggingFace CLI uses 'hf auth login' instead of 'hf login'"""
        return ["auth", "login"]

    def get_logout_args(self):
        """HuggingFace CLI uses 'hf auth logout' instead of 'hf logout'"""
        return ["auth", "logout"]

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

    def create_repository(self, name, organization, tag):
        if '/' in organization:
            return HuggingfaceRepositoryModel(name, organization, tag)
        else:
            return HuggingfaceRepository(name, organization, tag)

    def get_cli_download_args(self, directory_path, model):
        raise NotImplementedError("huggingface cli download not available")

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
        return False

    def push(self, _, args):
        if not self.hf_cli_available:
            raise NotImplementedError(self.get_missing_message())
        proc = run_cmd(
            [
                "hf",
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
        return "", []
