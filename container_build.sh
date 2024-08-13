#!/bin/bash

available() {
  command -v "$1" >/dev/null
}

select_container_manager() {
  if available podman; then
    conman_bin="podman"
    return 0
  elif available docker; then
    conman_bin="docker"
    return 0
  fi

  conman_bin="podman"
}

get_llm_store() {
  if [ "$EUID" -eq 0 ]; then
    llm_store="/var/lib/ramalama/storage"
    return 0
  fi

  llm_store="$HOME/.local/share/ramalama/storage"
}

add_build_platform() {
  conman_build+=("build" "--platform" "$platform")
  conman_build+=("-t" "quay.io/ramalama/$image_name" ".")
}

build() {
  cd "$1"
  local image_name
  image_name=$(echo "$1" | sed "s#/#:#g" | sed "s#container-images:##g")
  local conman_build=("${conman[@]}")
  if [ "$#" -lt 2 ]; then
    add_build_platform
    "${conman_build[@]}"
  elif [ "$2" = "-d" ]; then
    add_build_platform
    echo "${conman_build[@]}"
  elif [ "$2" = "push" ]; then
    "${conman[@]}" push "quay.io/ramalama/$image_name"
  else
    add_build_platform
    "${conman_build[@]}"
  fi

  cd - > /dev/null
}

main() {
  set -eu -o pipefail

  local conman_bin
  select_container_manager
  local conman=("$conman_bin")
  local platform="linux/amd64"
  if [ "$(uname -m)" = "aarch64" ]; then
    platform="linux/arm64"
  fi

  for i in container-images/*/*; do
    build "$i" "$@"
  done
}

main "$@"

