#!/usr/bin/python3

import os
import sys
import subprocess
import json

def run_command(args):
    try:
        subprocess.run(args, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(args)}")
        print(e)
        sys.exit(1)

def pull_cli(ramalama_store, model):
    registry_scheme = "https"
    registry = "registry.ollama.ai"
    model = "library/" + model
    accept = "Accept: application/vnd.docker.distribution.manifest.v2+json"
    if ':' in model:
        model_name, model_tag = model.split(':', 1)
    else:
        model_name = model
        model_tag = "latest"

    manifests = os.path.join(ramalama_store, "manifests", registry, model_name, model_tag)
    os.makedirs(os.path.dirname(manifests), exist_ok=True)
    os.makedirs(os.path.join(ramalama_store, "blobs"), exist_ok=True)

    curl_command = [
        "curl", "-s", "--header", accept,
        "-o", manifests,
        f"{registry_scheme}://{registry}/v2/{model_name}/manifests/{model_tag}"
    ]
    run_command(curl_command)

    with open(manifests, 'r') as f:
        manifest_data = json.load(f)

    cfg_hash = manifest_data["config"]["digest"]
    config_blob_path = os.path.join(ramalama_store, "blobs", cfg_hash)
    curl_command = [
        "curl", "-s", "-L", "-C", "-", "--header", accept,
        "-o", config_blob_path,
        f"{registry_scheme}://{registry}/v2/{model_name}/blobs/{cfg_hash}"
    ]
    run_command(curl_command)

    progress_bar = ""
    print(manifest_data)
    for layer in manifest_data["layers"]:
        layer_digest = layer["digest"]
        if layer["mediaType"] == 'application/vnd.ollama.image.model':
            progress_bar = "--progress-bar"

        layer_blob_path = os.path.join(ramalama_store, "blobs", layer_digest)
        curl_command = [
            "curl", "-L", "-C", "-", progress_bar, "--header", accept,
            "-o", layer_blob_path,
            f"{registry_scheme}://{registry}/v2/{model_name}/blobs/{layer_digest}"
        ]
        run_command(curl_command)
        progress_bar = ""

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
        pull_cli(ramalama_store + "/repos/ollama", sys.argv[2])
    else:
        usage()

if __name__ == "__main__":
    main()

