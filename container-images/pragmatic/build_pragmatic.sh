#!/bin/bash

clone_and_build_pragmatic() {
  git clone https://github.com/redhat-et/PRAGmatic
  cd PRAGmatic
  git submodule update --init --recursive
  local url="https://download.pytorch.org/whl"
  if [ "$2" == "docling" ]; then
      ${PYTHON_VERSION} pip install docling --extra-index-url "$url/$1"
      ${PYTHON_VERSION} pip install -r requirements.txt --prefix=/usr
  else
      ${PYTHON_VERSION} pip install torch --extra-index-url "$url/$1"
      local tmpfile
      tmpfile=$(mktemp)
      grep -v docling requirements.txt > "${tmpfile}"
      ${PYTHON_VERSION} pip install -r "${tmpfile}" --prefix=/usr
      rm "${tmpfile}"
  fi

  ${PYTHON_VERSION} pip install --prefix=/usr .
  cd ..
}

main() {
    set -exu -o pipefail

    export PYTHON_VERSION="python3 -m"
    if [ "$(python3 --version)" \< "Python 3.11" ]; then
        dnf install -y python3.11 python3.11-pip git
        export PYTHON_VERSION="/usr/bin/python3.11 -m"
    else
        dnf install -y python3-pip git
    fi

    clone_and_build_pragmatic "$1" "$2"
    rm -rf /var/cache/*dnf* /opt/rocm-*/lib/*/library/*gfx9* /root/.cache \
      /root/buildinfo PRAGmatic
    dnf -y clean all
    ldconfig
}

main "$@"

