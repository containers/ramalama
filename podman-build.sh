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

build() {
  cd "$1"
  local image_name
  image_name=$(echo "$1" | sed "s#/#:#g" | sed "s#container-images:##g")
  if [ "$2" == "-d" ]; then
    echo "${conman[@]} -t quay.io/ramalama/$image_name ."
  else
    "${conman[@]}" -t quay.io/ramalama/$image_name .
  fi

  cd - > /dev/null
}

main() {
  set -eu -o pipefail

  local conman_bin
  select_container_manager
  local llm_store
  get_llm_store
  local conman=("$conman_bin" "--root" "$llm_store")
  local platform="linux/amd64"
  if [ "$(uname -m)" = "aarch64" ]; then
    platform="linux/arm64"
  fi

  conman+=("build" "--platform" "$platform")
  for i in container-images/*/*; do
    build "$i" "$@"
  done
}

main "@"

