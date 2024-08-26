#!/bin/bash

available() {
  command -v "$1" > /dev/null
}

main() {
  set -ex -o pipefail

  local maybe_sudo=""
  if [ "$EUID" -ne 0 ]; then
    maybe_sudo="sudo"
  fi

  local os
  os="$(uname -s)"
  if ! available autopep8; then
    if [ "$os" = "Linux" ]; then
      if available apt; then
        $maybe_sudo apt install -y python3-autopep8
      else
        $maybe_sudo dnf install -y python3-autopep8
      fi
    fi
  fi

  binfile=ramalama.py
  chmod +x ${binfile} install.py

  # only for macOS for now, which doesn't have containers
  if [ "$os" == "Darwin" ]; then
    /usr/bin/python3 --version
    pip install "huggingface_hub[cli]==0.24.2"
    huggingface-cli --help
    pip install "omlmd==0.1.4"
    omlmd --help
    ./install.py # todo macos support
  else
    ./container_build.sh
    autopep8 --in-place --exit-code *.py ramalama/*py # Check style is correct
    shellcheck -- *.sh
    $maybe_sudo ./install.py # todo macos support
  fi


  set +o pipefail
  ./${binfile} -h | grep Usage:
  set -o pipefail

  ./${binfile} version
  ./${binfile} pull ollama://tinyllama
  RAMALAMA_TRANSPORT=ollama ./${binfile} pull ben1t0/tiny-llm
  ./${binfile} pull ollama://tinyllama:1.1b
  ./${binfile} pull huggingface://afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k.gguf
  ./${binfile} pull oci://quay.io/mmortari/gguf-py-example:v1
  ./${binfile} list | grep tinyllama
  ./${binfile} list | grep tiny-vicuna-1b
  ./${binfile} list | grep NAME
  ./${binfile} list | grep oci://quay.io/mmortari/gguf-py-example/v1/example.gguf
#  ramalama list | grep granite-code
#  ramalama rm granite-code
}

main
