#!/bin/bash

available() {
  command -v "$1" > /dev/null
}

mac_steps() {
  ./install.py
}

linux_steps() {
  ./container_build.sh
  shellcheck -- *.sh
  if [ -n "$BRANCH" ]; then
    $maybe_sudo BRANCH=$BRANCH ./install.py
    return
  fi

  $maybe_sudo ./install.py
}

tests() {
  set +o pipefail
  ./${binfile} -h | grep usage:
  set -o pipefail

  ./${binfile} version
  ./${binfile} pull ollama://tinyllama
  RAMALAMA_TRANSPORT=ollama ./${binfile} pull ben1t0/tiny-llm
  ./${binfile} pull ollama://tinyllama:1.1b
  ./${binfile} pull huggingface://afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k.gguf
  ./${binfile} pull oci://quay.io/mmortari/gguf-py-example:v1
  ./${binfile} list --noheading
  ./${binfile} list -n
  ./${binfile} list --json
  ./${binfile} list --help
  ./${binfile} list | grep tinyllama
  ./${binfile} list | grep tiny-vicuna-1b
  ./${binfile} list | grep NAME
  ./${binfile} ls | grep tinyllama
  ./${binfile} ls | grep tiny-vicuna-1b
  ./${binfile} ls | grep NAME
  ./${binfile} ls | grep oci://quay.io/mmortari/gguf-py-example/v1/example.gguf
}

main() {
  set -ex -o pipefail

  local maybe_sudo=""
  if [ "$EUID" -ne 0 ]; then
    maybe_sudo="sudo"
  fi

  local os
  os="$(uname -s)"
  binfile=ramalama.py
  chmod +x ${binfile} install.py
  uname -a
  /usr/bin/python3 --version
  if [ -n "$GITHUB_HEAD_REF" ]; then
    export BRANCH="$GITHUB_HEAD_REF"
  elif [ -n "$GITHUB_REF_NAME" ]; then
    export BRANCH="$GITHUB_REF_NAME"
  fi

  pip install codespell
  pip install autopep8
  autopep8 --in-place --exit-code *.py ramalama/*py # Check style is correct
  if [ "$os" == "Darwin" ]; then
    mac_steps
  else
    linux_steps
  fi

  tests
}

main
