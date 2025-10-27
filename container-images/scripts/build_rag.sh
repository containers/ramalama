#!/bin/bash

install_pkgs() {
    local pkgs=("git-core" "libglvnd-glx")

    if [ "$backend" = "cu128" ]; then
        pkgs+=("python3.12" "python3.12-devel" "libcudnn9-devel-cuda-12" "libcusparselt0" "cuda-cupti-12-*")
        ln -sf python3.12 /usr/bin/python3
    elif [ "$backend" = "rocm6.3" ]; then
        pkgs+=("python3" "python3-devel" "uv" "rocm-core" "hipblas" "rocblas" "rocm-hip")
    elif [ "$backend" = "xpu" ]; then
        pkgs+=("python3" "python3-devel" "uv" "oneapi-level-zero" "intel-level-zero")
    elif [ "$backend" = "cpu" ]; then
        pkgs+=("python3" "python3-devel" "uv")
    else
        echo "Unsupported torch backend: $backend"
        exit 1
    fi

    dnf -y --nodocs --setopt=install_weak_deps=false install "${pkgs[@]}"
    dnf -y clean all
}

install_requirements() {
    if [ "$backend" = "cu128" ]; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        # shellcheck disable=SC1091
        source /root/.local/bin/env
    fi
    uv venv "$VIRTUAL_ENV"
    if [ -f "/var/tmp/requirements-rag-$backend-$(uname -m).txt" ]; then
        uv pip sync "/var/tmp/requirements-rag-$backend-$(uname -m).txt"
    else
        uv pip sync "/var/tmp/requirements-rag-$backend.txt"
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
