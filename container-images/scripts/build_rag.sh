#!/bin/bash

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
    dnf update -y
    dnf install -y "${python}" "${python}-pip" "${python}-devel" "${pkgs[@]}"
    if [[ "${python}" == "python3.11" ]]; then
	ln -sf /usr/bin/python3.11 /usr/bin/python3
    fi

    rm -rf /usr/local/python3.10
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

    local gpu="${1-cpu}"
    local python
    python=$(python_version)
    local pkgs=("git-core" "gcc" "gcc-c++")
    if [ "${gpu}" = "cuda" ]; then
        pkgs+=("libcudnn9-devel-cuda-12" "libcusparselt0" "cuda-cupti-12-*")
    fi

    if [[ "$ID" = "fedora" && "$VERSION_ID" -ge 42 ]] ; then
        pkgs+=("python3-sentencepiece-0.2.0")
    fi

    update_python
    to_gguf
    rag
    docling "${gpu}"

    dnf -y clean all
    rm -rf /var/cache/*dnf* /opt/rocm-*/lib/*/library/*gfx9* /root/.cache \
       /root/buildinfo
    ldconfig
}

main "$@"

