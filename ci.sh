#!/bin/bash

main() {
  set -ex -o pipefail

  ./podman-build.sh
  curl -fsSL https://raw.githubusercontent.com/containers/ramalama/main/install.sh | sudo bash

  set +o pipefail
  ramalama -h | grep Usage:
  set -o pipefail

  ramalama pull granite
  ramalama list | grep granite
  ramalama rm granite
  shellcheck "$(command -v ramalama)"
}

main
