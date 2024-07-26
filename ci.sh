#!/bin/bash

main() {
  set -ex -o pipefail

  ./podman-build.sh
  curl -fsSL https://raw.githubusercontent.com/containers/ramalama/main/install.sh | sudo bash

  set +o pipefail
  ./ramalama.py -h | grep Usage:
  set -o pipefail

  ramalama.py pull granite-code
#  ramalama list | grep granite-code
#  ramalama rm granite-code
}

main
