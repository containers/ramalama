#!/bin/bash
set -exu -o pipefail

GPU="${1-cpu}"

export PYTHON_VERSION="python3 -m"
pyversion=$(python3 --version)

version_greater() {
	string="$1
$2"
    [ "$string" != "$(sort --version-sort <<< "$string")" ]
}

packages=""
if [ "${GPU}" = "cuda" ]; then
    packages="libcudnn9-devel-cuda-12 libcusparselt0 cuda-cupti-12\*"
fi

update_python() {
    if version_greater "$pyversion" "Python 3.10"; then
	eval dnf install -y python3-pip "${packages}"
    else
	eval dnf install -y python3.11 python3.11-pip "${packages}"
	export PYTHON_VERSION="/usr/bin/python3.11 -m"
	ln -sf /usr/bin/python3.11 /usr/bin/python3
    fi
}

docling() {
    ${PYTHON_VERSION} pip install wheel qdrant_client fastembed docling docling-core --extra-index-url https://download.pytorch.org/whl/"$1"
    # Preloads models (assumes its installed from container_build.sh)
    doc2rag load
}

rag() {
    ${PYTHON_VERSION} pip install wheel qdrant_client fastembed openai fastapi uvicorn
    rag_framework load
}

update_python

rag
docling "${GPU}"

dnf -y clean all
rm -rf /var/cache/*dnf* /opt/rocm-*/lib/*/library/*gfx9* /root/.cache \
   /root/buildinfo
ldconfig
