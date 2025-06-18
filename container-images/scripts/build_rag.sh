#!/bin/bash

available() {
  command -v "$1" >/dev/null
}

python_version() {
  pyversion=$(python3 --version)
  # $2 is empty when no Python is installed, so just install python3
  if [ -n "$pyversion" ]; then
      string="$pyversion
Python 3.10"
      if [ "$string" == "$(sort --version-sort <<< "$string")" ]; then
	  echo "python3.11"
	  return
      fi
  fi

  echo "python3"
}

version_greater() {
    string="$1
$2"
    [ "$string" != "$(sort --version-sort <<< "$string")" ]
}

update_python() {
    if available dnf; then
        dnf update -y --allowerasing
        dnf install -y "${python}" "${python}-pip" "${python}-devel" "${pkgs[@]}"
        if [[ "${python}" == "python3.11" ]]; then
            ln -sf /usr/bin/python3.11 /usr/bin/python3
        fi
        rm -rf /usr/local/python3.10
    elif available apt-get; then
        apt-get update
        apt-get install -y "${python}" "${python}-pip" "${python}-dev" "${pkgs[@]}"
    fi
}

docling() {
    ${python} -m pip install --prefix=/usr docling docling-core accelerate --extra-index-url https://download.pytorch.org/whl/"$1"
    # Preloads models (assumes its installed from container_build.sh)
    doc2rag load
}

rag() {
    ${python} -m pip install --prefix=/usr wheel qdrant_client fastembed openai fastapi uvicorn
    rag_framework load
}

to_gguf() {
    ${python} -m pip install --prefix=/usr "numpy~=1.26.4" "sentencepiece~=0.2.0" "transformers>=4.45.1,<5.0.0" git+https://github.com/ggml-org/llama.cpp#subdirectory=gguf-py "protobuf>=4.21.0,<5.0.0"
}

main() {
    set -exu -o pipefail

    # shellcheck disable=SC1091
    source /etc/os-release

    local arch
    arch="$(uname -m)"
    local gpu="${1-cpu}"
    local python
    python=$(python_version)
    local pkgs
    if available dnf; then
        pkgs=("git-core" "gcc" "gcc-c++")
    else
        pkgs=("git" "gcc" "g++")
    fi
    if [ "${gpu}" = "cuda" ]; then
        pkgs+=("libcudnn9-devel-cuda-12" "libcusparselt0" "cuda-cupti-12-*")
    fi

    if [[ "$ID" = "fedora" && "$VERSION_ID" -ge 42 ]] ; then
        pkgs+=("python3-sentencepiece-0.2.0")
    fi

    update_python
    to_gguf

    # Temporarily disable build for s390x
    if [[ "$arch" != "s390x" ]]; then
        rag
        docling "${gpu}"
    else
        echo "skipping rag and docling build for s390x architecture: build temporarily disabled."
    fi

    if available dnf; then
        dnf -y clean all
        rm -rf /var/cache/*dnf* /opt/rocm-*/lib/*/library/*gfx9* /root/.cache \
        /root/buildinfo
    elif available apt-get; then
        apt-get clean
        rm -rf /var/lib/apt/lists/*
    fi
    ldconfig
}

main "$@"

