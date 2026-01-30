#!/bin/bash

install_pkgs() {
    local pkgs=("git-core" "libglvnd-glx")
    local default_python="python3.13"

    if [ "$backend" = "cu128" ]; then
        default_python="python3.12"
        pkgs+=("libcudnn9-devel-cuda-12" "libcusparselt0" "cuda-cupti-12-*")
    elif [ "$backend" = "rocm6.3" ]; then
        pkgs+=("uv" "rocm-core" "hipblas" "rocblas" "rocm-hip")
    elif [ "$backend" = "xpu" ]; then
        pkgs+=("uv" "oneapi-level-zero" "intel-level-zero")
    elif [ "$backend" = "cpu" ]; then
        pkgs+=("uv")
    else
        echo "Unsupported torch backend: $backend"
        exit 1
    fi
    pkgs+=("$default_python" "${default_python}-devel")

    dnf -y --nodocs --setopt=install_weak_deps=false install "${pkgs[@]}"
    dnf -y clean all

    if [ "$backend" = "cu128" ]; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        # shellcheck disable=SC1091
        source /root/.local/bin/env
    fi
    uv venv --python "/usr/bin/$default_python" "$VIRTUAL_ENV"
}

install_requirements() {
    local script_dir
    script_dir="$(dirname "$0")"
    if [ -f "$script_dir/../common/requirements-rag-$backend-$(uname -m).txt" ]; then
        uv pip install -r "$script_dir/../common/requirements-rag-$backend-$(uname -m).txt"
    else
        uv pip install -r "$script_dir/../common/requirements-rag-$backend.txt"
    fi
}

load_models() {
    uv run rag_framework load
    uv run doc2rag load
}

main() {
    set -exu -o pipefail
    local backend="${1-cpu}"

    install_pkgs
    install_requirements
    load_models
    ldconfig
}

main "$@"
