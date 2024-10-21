#!/bin/bash

set -euo pipefail

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

add_build_platform() {
  conman_build+=("build" "--platform" "$platform")
  conman_build+=("-t" "quay.io/ramalama/$image_name" ".")
}

rm_container_image() {
  if [ "$image_name" == "cuda" ] || [ "$image_name" == "rocm" ]; then
    "$conman_bin" rmi -f "$image_name" || true
  fi
}

build() {
  cd "$1"
  local image_name
  image_name=$(echo "$1" | sed "s#container-images/##g")
  local conman_build=("${conman[@]}")
  if [ "$#" -lt 2 ]; then
    add_build_platform
    "${conman_build[@]}"
    rm_container_image
  elif [ "$2" = "-d" ]; then
    add_build_platform
    echo "${conman_build[@]}"
  elif [ "$2" = "push" ]; then
    "${conman[@]}" push "quay.io/ramalama/$image_name"
  elif [ "$2" = "log" ]; then
    "${conman_build[@]}" 2>&1 | tee container_build.log
  else
    add_build_platform
    "${conman_build[@]}"
    rm_container_image
  fi

  cd - > /dev/null
}

main() {
  set -eu -o pipefail

  local conman_bin
  select_container_manager
  local conman=("$conman_bin")
  local platform="linux/amd64"
  if [ "$(uname -m)" = "aarch64" ] || ([ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]); then
    platform="linux/arm64"
  fi

  local target="${1:-all}"

  if [ "$target" = "--help" ]; then
    echo "Usage: $0 [all|image_name]"
    exit 0
  fi

  if [ "$target" = "all" ]; then
    for i in container-images/*; do
      build "$i" "${@:2}"
    done
  else
    build "container-images/$target" "${@:2}"
  fi
}

main "$@"
