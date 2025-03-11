#!/bin/bash

build_rag() {
    ${PYTHON_VERSION} pip install "qdrant-client[fastembed]"
    ${PYTHON_VERSION} pip install docling
    ${PYTHON_VERSION} pip install openai
}

main() {
    export PYTHON_VERSION="python3 -m"
    set -exu -o pipefail
    build_rag
    ldconfig
}

main "$@"
