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

fixup_gguf() {
    # Hermeto converts the https:// url used to reference gguf into a local file:// path, and
    # uv doesn't support the #subdirectory syntax when installing from a local file.
    # Repackage the gguf tarball so that the gguf-py directory is the root, and update the
    # checksum in the requirements file.
    if [ -f "/var/tmp/${backend}-$(uname -m)-pypi.org.txt" ]; then
        req_file="/var/tmp/${backend}-$(uname -m)-pypi.org.txt"
    else
        req_file="/var/tmp/${backend}-pypi.org.txt"
    fi
    # shellcheck disable=SC2034
    read -r name _ uri hash < <(grep "^gguf @" "$req_file")
    src_tarball="${uri#file://}"
    src_tarball="${src_tarball%#*}"
    tmpdir="$(mktemp -d)"
    pushd "$tmpdir"
    tar -xf "$src_tarball"
    cd llama.cpp-*
    dest_tarball="$(mktemp /var/tmp/gguf-XXXXXX.tar.gz)"
    tar -czf "$dest_tarball" gguf-py
    popd
    rm -rf "$tmpdir"
    sed -i -e "s,^gguf @ .*$,gguf @ file://$dest_tarball --hash=sha256:$(sha256sum "$dest_tarball" | cut -d" " -f1)," "$req_file"
}

install_requirements() {
    if [ "$backend" = "cu128" ]; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        # shellcheck disable=SC1091
        source /root/.local/bin/env
    fi
    uv venv "$VIRTUAL_ENV"
    local uv_args=()
    for index in pypi.org download.pytorch.org; do
        if [ -f "/var/tmp/${backend}-$(uname -m)-${index}.txt" ]; then
            uv_args+=("-r" "/var/tmp/${backend}-$(uname -m)-${index}.txt")
        elif [ -f "/var/tmp/${backend}-${index}.txt" ]; then
            uv_args+=("-r" "/var/tmp/${backend}-${index}.txt")
        else
            echo "No requirements file found for backend $backend and index $index"
            exit 1
        fi
        # Comment out the --index-url line to avoid a uv error
        sed -i -e 's/^--index/# &/' "${uv_args[-1]}"
    done
    if [ -v PIP_FIND_LINKS ]; then
        echo "Using prefetched dependencies from $PIP_FIND_LINKS"
        uv_args+=("--find-links" "$PIP_FIND_LINKS" "--offline")
        fixup_gguf
    else
        uv_args+=("--torch-backend" "$backend")
    fi
    uv pip install "${uv_args[@]}"

    # Cleanup tarball created by fixup_gguf
    rm -f /var/tmp/gguf-*.tar.gz
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
