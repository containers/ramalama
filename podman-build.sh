#!/bin/bash

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
    llm_store="/var/lib/podman-llm/storage"
    return 0
  fi

  llm_store="$HOME/.local/share/podman-llm/storage"
}

build() {
  cd "$1"
  local image_name
  image_name=$(echo "$1" | sed "s#/#:#g" | sed "s#container-images:##g")
  "${conman[@]}" build -t "quay.io/podman-llm/$image_name" .
  cd -
}

main() {
  set -exu -o pipefail

  local conman_bin
  select_container_manager
  local llm_store
  get_llm_store
  local conman=("$conman_bin" "--root" "$llm_store")
  for i in container-images/*/*; do
    build "$i"
  done
}

main

