#!/bin/bash

main() {
  set -ex -o pipefail

  local uname_m
  uname_m="$(uname -m)"
  if [ "$uname_m" = "x86_64" ]; then
    local vllm_sha="a5dd03c1ebc5e4f56f3c9d3dc0436e9c582c978f"
    git clone https://github.com/vllm-project/vllm
    cd vllm
    git reset --hard "$vllm_sha"
    export PATH="/root/.local/bin:$PATH"
    uv pip install --upgrade pip
    uv pip install "cmake>=3.26.1" wheel packaging ninja "setuptools-scm>=8" numpy
    uv pip install -v -r requirements/cpu.txt --extra-index-url https://download.pytorch.org/whl/cpu
    VLLM_TARGET_DEVICE=cpu python setup.py install
    cd -
    rm -rf vllm
  fi
}

main "$@"

