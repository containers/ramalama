import json
import os
import urllib.request
from collections.abc import Callable
from typing import Any

from ramalama.common import perror, run_cmd, verify_checksum
from ramalama.http_client import download_file
from ramalama.logger import logger


def fetch_manifest_data(registry_head: str, model_tag: str, accept: str) -> dict:
    """
    Fetch manifest data for a model from a registry.

    Args:
        registry_head: Base URL for the registry API
        model_tag: Tag of the model to fetch
        accept: Accept header for the request

    Returns:
        Manifest data as JSON
    """
    url = f"{registry_head}/manifests/{model_tag}"
    headers = {"Accept": accept}

    logger.debug(f"Fetching manifest data from url {url}")
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request) as response:
        manifest_data = json.load(response)
    return manifest_data


def pull_config_blob(repos: str, accept: str, registry_head: str, manifest_data: dict[str, Any]) -> None:
    """
    Pull configuration blob for a model.

    Args:
        repos: Repository base directory
        accept: Accept header for the request
        registry_head: Base URL for the registry API
        manifest_data: Manifest data for the model
        show_progress: Whether to show download progress
    """
    cfg_hash = manifest_data["config"]["digest"]
    config_blob_path = os.path.join(repos, "blobs", cfg_hash)

    os.makedirs(os.path.dirname(config_blob_path), exist_ok=True)

    url = f"{registry_head}/blobs/{cfg_hash}"
    headers = {"Accept": accept}
    download_file(url, config_blob_path, headers=headers, show_progress=False)


def pull_blob(
    repos: str,
    layer_digest: str,
    accept: str,
    registry_head: str,
    model_name: str,
    model_tag: str,
    model_path: str,
    show_progress: bool,
    in_existing_cache_fn: Callable | None = None,
):
    """
    Pull a blob for a model layer.

    Args:
        repos: Repository base directory
        layer_digest: Digest of the layer to pull
        accept: Accept header for the request
        registry_head: Base URL for the registry API
        models: Models directory
        model_name: Name of the model
        model_tag: Tag of the model
        model_path: Target path for the model
        show_progress: Whether to show download progress
        in_existing_cache_fn: Function to check if blob exists in cache

    Raises:
        ValueError: If checksum verification fails
    """
    layer_blob_path = os.path.join(repos, "blobs", layer_digest)
    url = f"{registry_head}/blobs/{layer_digest}"
    headers = {"Accept": accept}

    local_blob = None
    if in_existing_cache_fn:
        local_blob = in_existing_cache_fn(model_name, model_tag)

    if local_blob is not None:
        run_cmd(["ln", "-sf", local_blob, layer_blob_path])
    else:
        download_file(url, layer_blob_path, headers=headers, show_progress=show_progress)
        # Verify checksum after downloading the blob
        if not verify_checksum(layer_blob_path):
            perror(f"Checksum mismatch for blob {layer_blob_path}, retrying download ...")
            os.remove(layer_blob_path)
            download_file(url, layer_blob_path, headers=headers, show_progress=True)
            if not verify_checksum(layer_blob_path):
                raise ValueError(f"Checksum verification failed for blob {layer_blob_path}")

    relative_target_path = os.path.relpath(layer_blob_path, start=os.path.dirname(model_path))
    run_cmd(["ln", "-sf", relative_target_path, model_path])
