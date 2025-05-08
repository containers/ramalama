#!/bin/bash
set -exu -o pipefail
# shellcheck disable=SC1091
source /etc/os-release

GPU="${1-cpu}"

python_version() {
  pyversion=$(python3 --version)
  # $2 is empty when no Python is installed, so just install python3
  if [ -n "$pyversion" ]; then
      string="$pyversion
Python 3.11"
      if [ "$string" == "$(sort --version-sort <<< "$string")" ]; then
	  echo "python3.11"
	  return
      fi
  fi
  echo "python3"
}

export PYTHON
PYTHON=$(python_version)

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
    eval dnf install -y "${PYTHON}" "${PYTHON}-pip" "${PYTHON}-devel" "${packages}"
    if [[ "${PYTHON}" == "python3.11" ]]; then
	ln -sf /usr/bin/python3.11 /usr/bin/python3
    fi
}

docling() {
    ${PYTHON} -m pip install --prefix=/usr docling docling-core accelerate --extra-index-url https://download.pytorch.org/whl/"$1"
    # Preloads models (assumes its installed from container_build.sh)
    doc2rag load
}

rag() {
    ${PYTHON} -m pip install --prefix=/usr wheel qdrant_client fastembed openai fastapi uvicorn
    rag_framework load
}

to_gguf() {
    ${PYTHON} -m pip install --prefix=/usr "numpy~=1.26.4" "sentencepiece~=0.2.0" "transformers>=4.45.1,<5.0.0" git+https://github.com/ggml-org/llama.cpp#subdirectory=gguf-py "protobuf>=4.21.0,<5.0.0"
}

update_python

to_gguf
rag
docling "${GPU}"

dnf -y clean all
rm -rf /var/cache/*dnf* /opt/rocm-*/lib/*/library/*gfx9* /root/.cache \
   /root/buildinfo
ldconfig
