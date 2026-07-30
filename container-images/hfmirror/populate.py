#!/usr/bin/env python3
"""Download test models from Hugging Face into a local models/ directory tree.

Requires HF_TOKEN to be set (or passed via --token).

Usage: python populate.py [--models-dir DIR] [--token TOKEN]
"""

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from huggingface_hub import hf_hub_download  # type: ignore[import-not-found]


MODELS = [
    ("Felladrin/gguf-smollm-360M-instruct-add-basics", [
        "smollm-360M-instruct-add-basics.IQ2_XXS.gguf",
    ]),
    ("ggml-org/SmolVLM-256M-Instruct-GGUF", [
        "SmolVLM-256M-Instruct-Q8_0.gguf",
        "mmproj-SmolVLM-256M-Instruct-Q8_0.gguf",
    ]),
    ("owalsh/SmolLM2-135M-Instruct-GGUF-Split", [
        "Q4_0/SmolLM2-135M-Instruct-Q4_0-00001-of-00003.gguf",
        "Q4_0/SmolLM2-135M-Instruct-Q4_0-00002-of-00003.gguf",
        "Q4_0/SmolLM2-135M-Instruct-Q4_0-00003-of-00003.gguf",
    ]),
    ("HuggingFaceTB/smollm-135M-instruct-v0.2-Q8_0-GGUF", [
        "smollm-135m-instruct-add-basics-q8_0.gguf",
    ]),
    ("taronaeo/tinyllamas-BE", [
        "stories260K-be.gguf",
    ]),
    ("ggml-org/gemma-3-270m-it-qat-GGUF", [
        "gemma-3-270m-it-qat-Q4_0.gguf",
    ]),
    ("TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF", [
        "tinyllama-1.1b-chat-v1.0.Q2_K.gguf",
        "config.json",
    ]),
    ("mlx-community/Llama-3.2-1B-Instruct-4bit", [
        "config.json",
        "model.safetensors",
        "special_tokens_map.json",
        "tokenizer.json",
        "tokenizer_config.json",
    ]),
    ("LiheYoung/depth-anything-small-hf", [
        "model.safetensors",
        "config.json",
    ]),
]


def download_file(repo_id, filename, models_dir, token):
    org, repo = repo_id.split("/", 1)
    dest_dir = models_dir / org / repo
    dest = dest_dir / filename
    if dest.exists():
        print(f"  SKIP  {repo_id}/{filename}", flush=True)
        return
    print(f"  FETCH {repo_id}/{filename}", flush=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=str(dest_dir),
        token=token,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models-dir", type=Path, default=Path(__file__).parent / "models")
    parser.add_argument("--token", default=os.environ.get("HF_TOKEN"))
    args = parser.parse_args()

    if not args.token:
        print("Error: HF_TOKEN environment variable or --token required", file=sys.stderr)
        sys.exit(1)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = []
        for repo_id, files in MODELS:
            for filename in files:
                futures.append(pool.submit(download_file, repo_id, filename, args.models_dir, args.token))
        for future in as_completed(futures):
            future.result()

    print(f"Done. Models in {args.models_dir}/")


if __name__ == "__main__":
    main()
