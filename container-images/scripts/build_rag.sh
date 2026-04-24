#!/bin/bash

install_pkgs() {
    local default_python="python3.14"
    local pkgs=("uv" "$default_python" "${default_python}-devel")

    dnf -y --nodocs --setopt=install_weak_deps=false install "${pkgs[@]}"
    dnf -y clean all

    uv venv --python "/usr/bin/$default_python" "$VIRTUAL_ENV"
}

install_requirements() {
    local script_dir
    script_dir="$(dirname "$0")"
    uv pip install -r "$script_dir/../common/requirements-rag.txt"
}

main() {
    set -exu -o pipefail

    install_pkgs
    install_requirements
}

main "$@"
