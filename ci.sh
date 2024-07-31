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
  os="$(uname)"
  if ! available autopep8; then
    if [ "$os" = "Linux" ]; then
      if available apt; then
        $maybe_sudo apt install -y python3-autopep8
      else
        $maybe_sudo dnf install -y python3-autopep8
      fi
    fi
  fi

  pip install "huggingface_hub[cli]==0.24.2"

  chmod +x ramalama install.sh
  if [ "$os" = "Linux" ]; then
    ./container_build.sh
    $maybe_sudo ./install.sh # todo macos support
    autopep8 --exit-code ramalama # Check style is correct
    shellcheck -- *.sh
  fi

  set +o pipefail
  ./ramalama -h | grep Usage:
  set -o pipefail

  ./ramalama pull tinyllama
  ./ramalama pull huggingface://afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k.gguf
  ./ramalama list | grep tinyllama
  ./ramalama list | grep tiny-vicuna-1b
  ./ramalama list | grep NAME
#  ramalama list | grep granite-code
#  ramalama rm granite-code
}

main
