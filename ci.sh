#!/bin/bash

main() {
  set -ex -o pipefail

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
