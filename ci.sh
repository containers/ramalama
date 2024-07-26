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

  if ! available autopep8; then
     if available apt; then
	 $maybe_sudo apt install -y python3-autopep8
     else
	 $maybe_sudo dnf install -y python3-autopep8
     fi
  fi

  ./container_build.sh
  curl -fsSL https://raw.githubusercontent.com/containers/ramalama/main/install.sh | sudo bash

  set +o pipefail
  chmod +x ramalama
  ./ramalama -h | grep Usage:
  set -o pipefail

  ./ramalama pull tinyllama
  autopep8 --exit-code ramalama # Check style is correct
#  ramalama list | grep granite-code
#  ramalama rm granite-code
}

main
