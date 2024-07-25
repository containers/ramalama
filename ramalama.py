#!/usr/bin/python3

import os
import sys
import subprocess
import json
import hashlib


def verify_checksum(filename):
    """
    Verifies if the SHA-256 checksum of a file matches the checksum provided in the filename.

    Args:
    filename (str): The filename containing the checksum prefix (e.g., "sha256:<checksum>")

    Returns:
    bool: True if the checksum matches, False otherwise.
    """

    if not os.path.exists(filename):
        return False

    # Check if the filename starts with "sha256:"
    fn_base = os.path.basename(filename)
    if not fn_base.startswith("sha256:"):
        raise ValueError(f"Filename does not start with 'sha256:': {fn_base}")

    # Extract the expected checksum from the filename
    expected_checksum = fn_base.split(":")[1]
    if len(expected_checksum) != 64:
        raise ValueError("Invalid checksum length in filename")

    # Calculate the SHA-256 checksum of the file contents
    sha256_hash = hashlib.sha256()
    with open(filename, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    # Get the calculated checksum
    calculated_checksum = sha256_hash.hexdigest()

    # Compare the checksums
    return calculated_checksum == expected_checksum


def run_command(args):
    try:
        subprocess.run(args, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(args)}")
        print(e)
        sys.exit(1)


def run_curl_command(args, filename):
    if not verify_checksum(filename):
        run_command(args)


def pull_ollama_manifest(ramalama_store, manifests, accept, registry_head, model_tag):
    os.makedirs(os.path.dirname(manifests), exist_ok=True)
    os.makedirs(os.path.join(ramalama_store, "blobs"), exist_ok=True)
    curl_command = [
        "curl", "-s", "--header", accept,
        "-o", manifests,
        f"{registry_head}/manifests/{model_tag}"
    ]
    run_command(curl_command)


def pull_ollama_config_blob(ramalama_store, accept, registry_head, manifest_data):
    cfg_hash = manifest_data["config"]["digest"]
    config_blob_path = os.path.join(ramalama_store, "blobs", cfg_hash)
    curl_command = [
        "curl", "-s", "-L", "-C", "-", "--header", accept,
        "-o", config_blob_path,
        f"{registry_head}/blobs/{cfg_hash}"
    ]
    run_curl_command(curl_command, config_blob_path)


def pull_ollama_blob(ramalama_store, layer_digest, accept, registry_head, ramalama_models, model_name, model_tag, symlink_path):
    layer_blob_path = os.path.join(ramalama_store, "blobs", layer_digest)
    curl_command = ["curl", "-L", "-C", "-", "--progress-bar", "--header",
                    accept, "-o", layer_blob_path, f"{registry_head}/blobs/{layer_digest}"]
    run_curl_command(curl_command, layer_blob_path)
    os.makedirs(ramalama_models, exist_ok=True)
    relative_target_path = os.path.relpath(
        layer_blob_path, start=os.path.dirname(symlink_path))
    run_command(["ln", "-sf", relative_target_path, symlink_path])


def pull_cli(ramalama_store, ramalama_models, model):
    registry_scheme = "https"
    registry = "registry.ollama.ai"
    model = "library/" + model
    accept = "Accept: application/vnd.docker.distribution.manifest.v2+json"
    if ':' in model:
        model_name, model_tag = model.split(':', 1)
    else:
        model_name = model
        model_tag = "latest"

    model_base = os.path.basename(model_name)
    symlink_path = os.path.join(ramalama_models, f"{model_base}:{model_tag}")
    if os.path.exists(symlink_path):
        return

    manifests = os.path.join(ramalama_store, "manifests",
                             registry, model_name, model_tag)
    registry_head = f"{registry_scheme}://{registry}/v2/{model_name}"
    pull_ollama_manifest(ramalama_store, manifests,
                         accept, registry_head, model_tag)
    with open(manifests, 'r') as f:
        manifest_data = json.load(f)

    pull_ollama_config_blob(ramalama_store, accept,
                            registry_head, manifest_data)
    for layer in manifest_data["layers"]:
        layer_digest = layer["digest"]
        if layer["mediaType"] != 'application/vnd.ollama.image.model':
            continue

        pull_ollama_blob(ramalama_store, layer_digest, accept,
                         registry_head, ramalama_models, model_name, model_tag, symlink_path)


def usage():
    print("Usage:")
    print(f"  {os.path.basename(__file__)} COMMAND")
    print()
    print("Commands:")
    print("  pull MODEL       Pull a model")
    sys.exit(1)


def get_ramalama_store():
    if os.geteuid() == 0:
        return "/var/lib/ramalama"

    return os.path.expanduser("~/.local/share/ramalama")


def main():
    if len(sys.argv) < 2:
        usage()

    ramalama_store = get_ramalama_store()
    command = sys.argv[1]
    if command == "pull" and len(sys.argv) > 2:
        pull_cli(ramalama_store + "/repos/ollama",
                 ramalama_store + "/models/ollama", sys.argv[2])
    else:
        usage()


if __name__ == "__main__":
    main()
