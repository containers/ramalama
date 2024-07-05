#!/bin/bash

main() {
  set -ex -o pipefail

  ./podman-build.sh
  curl -fsSL https://raw.githubusercontent.com/ericcurtin/podman-llm/main/install.sh | sudo bash
  podman-llm -h | grep Usage:
  podman-llm pull granite
  podman-llm list | grep granite
  podman-llm rm granite
}

main
