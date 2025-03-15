#!/bin/bash

build_rag() {
    ${PYTHON_VERSION} -m pip install "qdrant-client[fastembed]"
    ${PYTHON_VERSION} -m pip install docling
    ${PYTHON_VERSION} -m pip install openai
    ${PYTHON_VERSION} rag_framework.py --load
}

main() {
    export PYTHON_VERSION="python3"
    set -exu -o pipefail
    build_rag
    ldconfig
}

main "$@"
