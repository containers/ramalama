#!/bin/bash
set -exu -o pipefail
# shellcheck disable=SC1091
source /etc/os-release

GPU="${1-cpu}"

export PYTHON_VERSION="python3 -m"
pyversion=$(python3 --version)

version_greater() {
	string="$1
$2"
    [ "$string" != "$(sort --version-sort <<< "$string")" ]
}

packages="git-core gcc gcc-c++"
if [ "${GPU}" = "cuda" ]; then
    packages+=" libcudnn9-devel-cuda-12 libcusparselt0 cuda-cupti-12\*"
fi

if [[ "$ID" = "fedora" && "$VERSION_ID" -ge 42 ]] ; then
    packages+=" python3-sentencepiece-0.2.0"

fi

update_python() {
    if version_greater "$pyversion" "Python 3.10"; then
	eval dnf install -y python3-pip python3-devel "${packages}"
    else
	eval dnf install -y python3.11 python3.11-pip python3.11-devel "${packages}"
	export PYTHON_VERSION="/usr/bin/python3.11 -m"
	ln -sf /usr/bin/python3.11 /usr/bin/python3
    fi
}

docling() {
    ${PYTHON_VERSION} pip install --prefix=/usr docling docling-core accelerate --extra-index-url https://download.pytorch.org/whl/"$1"
    # Preloads models (assumes its installed from container_build.sh)
    doc2rag load
}

rag() {
    ${PYTHON_VERSION} pip install --prefix=/usr wheel qdrant_client fastembed openai fastapi uvicorn
    rag_framework load
}

to_gguf() {
    ${PYTHON_VERSION} pip install --prefix=/usr "numpy~=1.26.4" "sentencepiece~=0.2.0" "transformers>=4.45.1,<5.0.0" git+https://github.com/ggml-org/llama.cpp#subdirectory=gguf-py "protobuf>=4.21.0,<5.0.0"
}

update_python

to_gguf
rag
docling "${GPU}"

dnf -y clean all
rm -rf /var/cache/*dnf* /opt/rocm-*/lib/*/library/*gfx9* /root/.cache \
   /root/buildinfo
ldconfig
