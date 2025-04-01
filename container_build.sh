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
  conman_build+=("-t" "$REGISTRY_PATH/${target}")
  conman_build+=("-f" "${target}/Containerfile" ".")
}

rm_container_image() {
  if $rm_after_build; then
    "$conman_bin" rmi -f "${target}" || true
  fi
}

add_entrypoint() {
    containerfile=$(mktemp)
    cat > "${containerfile}" <<EOF
FROM $2
ENTRYPOINT [ "/usr/bin/$3.sh" ]
EOF
echo "$1 build --no-cache -t $2-$3 -f ${containerfile} ."
eval "$1 build --no-cache -t $2-$3 -f ${containerfile} ."
rm "${containerfile}"
}

add_rag() {
    containerfile=$(mktemp)
    GPU=cpu
    case $2 in
	cuda)
	    GPU=cuda
	    ;;
	rocm*)
	    GPU=rocm
	    ;;
	*)
	    GPU=cpu
	    ;;
    esac
    cat > "${containerfile}" <<EOF
ARG REGISTRY_PATH=quay.io/ramalama
FROM ${REGISTRY_PATH}/$2

COPY --chmod=755 ../scripts/ /usr/bin/
USER root
RUN /usr/bin/build_rag.sh ${GPU}
ENTRYPOINT []
EOF
    echo "$1 build --no-cache -t ${REGISTRY_PATH}/$2-rag -f ${containerfile} ."
    eval "$1 build --no-cache -t ${REGISTRY_PATH}/$2-rag -f ${containerfile} ."
    rm "${containerfile}"
}

add_entrypoints() {
    add_entrypoint "$1" "$2" "whisper-server"
    add_entrypoint "$1" "$2" "llama-server"
}

build() {
  local target=${1}
  cd "container-images/"
  local conman_build=("${conman[@]}")
  local conman_show_size=("${conman[@]}" "images" "--filter" "reference=$REGISTRY_PATH/${target}")
  if [ "$dryrun" == "-d" ]; then
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
      echo "${conman_show_size[@]}"
      "${conman_show_size[@]}"
      if [ "$target" != "ramalama-ci" ]; then
	  add_entrypoints "${conman[@]}" "${REGISTRY_PATH}"/"${target}"
	  add_rag "${conman[@]}" "${target}"
	  rm_container_image
      fi
      ;;
    push)
      "${conman[@]}" push "$REGISTRY_PATH/${target}"
      ;;
    multi-arch)
      podman farm build -t "$REGISTRY_PATH"/"${target}" -f "${target}"/Containerfile .
      add_entrypoints "podman farm" "$REGISTRY_PATH"/"${target}"
      ;;
    *)
      echo "Invalid command: ${2:-}. Use 'build', 'push' or 'multi-arch'."
      return 1
      ;;
  esac

  cd - > /dev/null
}

determine_platform() {
  local platform
  case $conman_bin in
    podman)
      platform="$(podman info --format '{{ .Version.OsArch }}' 2>/dev/null)"
      ;;
    docker)
      platform="$(docker info --format '{{ .ClientInfo.Os }}/{{ .ClientInfo.Arch }}' 2>/dev/null)"
      ;;
  esac

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
      -c)
        ci="true"
        shift
        ;;
      -d)
        dryrun="$1"
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

  # build ramalama container image first, as other images inherit from it
  build "ramalama" "$command"
  for i in container-images/*; do
    i=$(basename "$i")
    # skip these directories
    if [[ "$i" =~ ^(scripts|ramalama)$ ]]; then
      continue
    fi

    # todo, trim and get building in CI again
    if $ci && [[ "$i" =~ ^rocm$ ]]; then
      continue
    fi

    # skip images that don't make sense for multi-arch builds
    if [ "$command" = "multi-arch" ]; then
      if [[ "$i" =~ ^(rocm|intel-gpu)$ ]]; then
        continue
      fi
    fi

    build "$i" "$command"
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
  echo "  -d           Dryrun, print podman commands but don't execute"
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
  local dryrun=""
  local rm_after_build="false"
  local ci="false"
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
    process_all_targets "$command"
  else
    build "$target" "$command"
  fi
}

REGISTRY_PATH=${REGISTRY_PATH:-quay.io/ramalama}
main "$@"
