import json
import os
import urllib.request

from ramalama.common import download_file, run_cmd, verify_checksum
from ramalama.logger import logger


def fetch_manifest_data(registry_head, model_tag, accept):
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


def pull_config_blob(repos, accept, registry_head, manifest_data):
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
    repos,
    layer_digest,
    accept,
    registry_head,
    model_name,
    model_tag,
    model_path,
    show_progress,
    in_existing_cache_fn=None,
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
            print(f"Checksum mismatch for blob {layer_blob_path}, retrying download ...")
            os.remove(layer_blob_path)
            download_file(url, layer_blob_path, headers=headers, show_progress=True)
            if not verify_checksum(layer_blob_path):
                raise ValueError(f"Checksum verification failed for blob {layer_blob_path}")

    relative_target_path = os.path.relpath(layer_blob_path, start=os.path.dirname(model_path))
    run_cmd(["ln", "-sf", relative_target_path, model_path])


def repo_pull(
    repos,
    accept,
    registry_head,
    model_name,
    model_tag,
    models,
    model_path,
    show_progress,
    media_type="application/vnd.ollama.image.model",
    in_existing_cache_fn=None,
):
    """
    Pull a model from a repository.

    Args:
        repos: Repository base directory
        accept: Accept header for the request
        registry_head: Base URL for the registry API
        model_name: Name of the model
        model_tag: Tag of the model
        models: Models directory
        model_path: Target path for the model
        model: Model identifier string
        show_progress: Whether to show download progress
        media_type: Media type of the layer to pull
        in_existing_cache_fn: Function to check if blob exists in cache

    Returns:
        Path to the pulled model
    """
    os.makedirs(models, exist_ok=True)
    manifest_data = fetch_manifest_data(registry_head, model_tag, accept)
    pull_config_blob(repos, accept, registry_head, manifest_data)

    for layer in manifest_data["layers"]:
        layer_digest = layer["digest"]
        if layer["mediaType"] != media_type:
            continue

        pull_blob(
            repos,
            layer_digest,
            accept,
            registry_head,
            model_name,
            model_tag,
            model_path,
            show_progress,
            in_existing_cache_fn,
        )

    return model_path
