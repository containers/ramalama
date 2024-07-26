#!/bin/bash

available() {
  command -v "$1" > /dev/null
}

main() {
  set -ex -o pipefail

  if ! available autopep8 && available apt; then
    apt install -y python3-autopep8
  fi

  ./podman-build.sh
  curl -fsSL https://raw.githubusercontent.com/containers/ramalama/main/install.sh | sudo bash

  set +o pipefail
  ./ramalama -h | grep Usage:
  set -o pipefail

  ramalama pull granite-code
  autopep8 --exit-code ramalama # Check style is correct
#  ramalama list | grep granite-code
#  ramalama rm granite-code
}

main
