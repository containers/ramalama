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

  # only for macOS for now, which doesn't have containers
  if [ "$os" != "Linux" ]; then
    /usr/bin/python3 --version
    pip install "huggingface_hub[cli]==0.24.2"
    huggingface-cli --help
    pip install "omlmd==0.1.2"
    omlmd --help
  fi

  chmod +x ramalama install.py
  if [ "$os" = "Linux" ]; then
    ./container_build.sh
    autopep8 --exit-code ramalama # Check style is correct
    shellcheck -- *.sh
  fi

  $maybe_sudo ./install.py # todo macos support

  set +o pipefail
  ./ramalama -h | grep Usage:
  set -o pipefail

  ./ramalama pull tinyllama
  ./ramalama pull ben1t0/tiny-llm
  ./ramalama pull ollama://tinyllama:1.1b
  ./ramalama pull huggingface://afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k.gguf
  ./ramalama pull oci://quay.io/mmortari/gguf-py-example:v1
  ./ramalama list | grep tinyllama
  ./ramalama list | grep tiny-vicuna-1b
  ./ramalama list | grep NAME
  ./ramalama list | grep oci://quay.io/mmortari/gguf-py-example/v1/example.gguf
#  ramalama list | grep granite-code
#  ramalama rm granite-code
}

main
