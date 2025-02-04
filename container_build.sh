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
  conman_build+=("build")

  # This build saves space
  if ! $rm_after_build; then
    conman_build+=("--no-cache")
  fi

  conman_build+=("--platform" "$platform")
  conman_build+=("-t" "$REGISTRY_PATH/$image_name")
  conman_build+=("-f" "$image_name/Containerfile" ".")
}

rm_container_image() {
  if $rm_after_build; then
    "$conman_bin" rmi -f "$image_name" || true
  fi
}

build() {
  cd "container-images"
  local image_name="${1//container-images\//}"
  local conman_build=("${conman[@]}")
  local conman_show_size=("${conman[@]}" "images" "--filter" "reference='$REGISTRY_PATH/$image_name'")
  if [ "$3" == "-d" ]; then
      add_build_platform
      echo "${conman_build[@]}"
      cd - > /dev/null
      return 0
  fi

  case "${2:-}" in
    build)
      add_build_platform
      echo "${conman_build[@]}"
      "${conman_build[@]}"
      "${conman_show_size[@]}"
      rm_container_image
      ;;
    push)
      "${conman[@]}" push "$REGISTRY_PATH/$image_name"
      ;;
    multi-arch)
      podman farm build -t "$REGISTRY_PATH"/"$image_name" -f "$image_name"/Containerfile .
      ;;
    *)
      echo "Invalid command: ${2:-}. Use 'build', 'push' or 'multi-arch'."
      return 1
      ;;
  esac

  cd - > /dev/null
}

determine_platform() {
  local platform="linux/amd64"
  if [ "$(uname -m)" = "aarch64" ] || { [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; }; then
    platform="linux/arm64"
  fi

  echo "$platform"
}

parse_arguments() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        print_usage
        exit 0
        ;;
      -d)
        option="$1"
        shift
        ;;
      -r)
        rm_after_build="true"
        shift
        ;;
      build|push|multi-arch)
        command="$1"
        shift
        ;;
      *)
        target="$1"
        shift
        ;;
    esac
  done
}

process_all_targets() {
  local command="$1"
  local option="$2"
  for i in container-images/*; do
    if [ "$i" == "container-images/scripts" ]; then
      continue
    fi
    if [ "$command" = "multi-arch" ] && [ !-f $"i"/.multi-arch ]; then
      continue
    fi
    build "$i" "$command" "$option"
  done
}

print_usage() {
  echo "Usage: $(basename "$0") [-h|--help] [-d] <command> [target]"
  echo
  echo "Commands:"
  echo "  build        Build the container images"
  echo "  push         Push the container images"
  echo "  multi-arch   Build and Push multi-arch images with podman farm"
  echo
  echo "Options:"
  echo "  -d           Some option description"
  echo "  -r           Remove container image after build"
  echo
  echo "Targets:"
  echo "  Specify the target container image to build or push"
  echo "  If no target is specified, all container images will be processed"
  echo "Destination Registry:"
  echo "  Override the target registry path by setting the env var REGISTRY_PATH"
  echo "  default - quay.io/ramalama"
}

main() {
  local conman_bin
  select_container_manager
  local conman=("$conman_bin")
  local platform
  platform=$(determine_platform)

  local target=""
  local command=""
  local option=""
  local rm_after_build="false"
  parse_arguments "$@"
  if [ -z "$command" ]; then
    echo "Error: command is required (build or push)"
    print_usage
    exit 1
  fi
  if [ "$command" = "multi-arch" ] && [ "$conman_bin" != "podman" ]; then
    echo "Error: command 'multi-arch' only works with podman farm"
    print_usage
    exit 1
  fi

  target="${target:-all}"
  if [ "$target" = "all" ]; then
    process_all_targets "$command" "$option"
  else
    build "container-images/$target" "$command" "$option"
  fi
}

REGISTRY_PATH=${REGISTRY_PATH:-quay.io/ramalama}
main "$@"

