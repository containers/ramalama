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
  if [ -n "${nocache}" ]; then
      conman_build+=("${nocache}")
  fi


  conman_build+=("--platform" "$platform")
  if [ -n "$version" ]; then
      conman_build+=("--build-arg" "VERSION=$version")
      conman_build+=("-t" "$REGISTRY_PATH/${target}-${version}")
  else
      conman_build+=("-t" "$REGISTRY_PATH/${target}")
  fi
  conman_build+=("-f" "container-images/${target}/Containerfile" ".")
}

rm_container_image() {
  if $rm_after_build; then
    "$conman_bin" rmi -f "${target}" || true
  fi
}

add_entrypoint() {
    tag=$2
    if [ -n "$4" ]; then
        tag=$tag-$4
    fi
    tag=$tag-$3
    containerfile="container-images/common/Containerfile.entrypoint"
    build_args=("--build-arg" "PARENT=$2" "--build-arg" "ENTRYPOINT=/usr/bin/${3}.sh")
    echo "$1 build ${nocache} ${build_args[*]} -t $tag -f ${containerfile} ."
    eval "$1 build ${nocache} ${build_args[*]} -t $tag -f ${containerfile} ."
}

add_rag() {
    tag="$2"
    if [ -n "$3" ]; then
        tag=$tag-$3
    fi
    tag=$tag-rag
    containerfile="container-images/common/Containerfile.rag"
    GPU=cpu
    case $2 in
	cuda)
	    GPU=cuda
	    ;;
	rocm*)
	    GPU=rocm
	    ;;
	musa)
	    GPU=musa
	    ;;
	*)
	    GPU=cpu
	    ;;
    esac
    build_args=("--build-arg" "PARENT=$2" "--build-arg" "GPU=$GPU")
    echo "$1 build ${nocache} ${build_args[*]} -t $tag -f ${containerfile} ."
    eval "$1 build ${nocache} ${build_args[*]} -t $tag -f ${containerfile} ."
}

add_entrypoints() {
    add_entrypoint "$1" "$2" "whisper-server" "$3"
    add_entrypoint "$1" "$2" "llama-server"   "$3"
}

build() {
  local target=${1}
  local version=${3:-}
  local conman_build=("${conman[@]}")
  local conman_show_size=("${conman[@]}" "images" "--filter" "reference=$REGISTRY_PATH/${target}")
  if [ "$dryrun" == "-d" ]; then
      add_build_platform
      echo "${conman_build[@]}"
      return 0
  fi

  case "${2:-}" in
    build)
      add_build_platform
      echo "${conman_build[@]}"
      "${conman_build[@]}"
      echo "${conman_show_size[@]}"
      "${conman_show_size[@]}"
      case ${target} in
	  ramalama-cli | llama-stack | openvino | bats)
	  ;;
	  *)
	      if [ "${build_all}" -eq 1 ]; then
		  add_entrypoints "${conman[@]}" "${REGISTRY_PATH}"/"${target}" "${version}"
		  add_rag "${conman[@]}" "${REGISTRY_PATH}"/"${target}" "${version}"
		  rm_container_image
	      fi
      esac
      ;;
    push)
      "${conman[@]}" push "$REGISTRY_PATH/${target}"
      ;;
    multi-arch)
      podman farm build -t "$REGISTRY_PATH"/"${target}" -f "${target}"/Containerfile .
      add_entrypoints "podman farm" "$REGISTRY_PATH"/"${target}" "${version}"
      ;;
    *)
      echo "Invalid command: ${2:-}. Use 'build', 'push' or 'multi-arch'."
      return 1
      ;;
  esac
}

determine_platform() {
  local platform
  case $conman_bin in
    podman)
      platform="$(podman info --format '{{ .Version.OsArch }}' 2>/dev/null)"
      ;;
    docker)
      if docker info --format '{{ .ClientInfo.Os }}' &>/dev/null; then
        platform="$(docker info --format '{{ .ClientInfo.Os }}/{{ .ClientInfo.Arch }}' 2>/dev/null)"
      else
        platform="$(docker info --format '{{ .OSType }}/{{ .Architecture }}' 2>/dev/null)"
      fi
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
      -C)
        nocache=""
        shift
        ;;
      -d)
        dryrun="$1"
        shift
        ;;
      -r)
        rm_after_build="true"
        nocache=""
        shift
        ;;
      -s) # Only build initial image
        build_all=0
        shift
        ;;
      -v)
        version="$2"
        shift
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
  for i in ./container-images/*; do
    i=$(basename "$i")
    # skip these directories
    if [[ "$i" =~ ^(scripts|ramalama|common)$ ]]; then
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
  echo "  -h           Print help information"
  echo "  -c           Do not use cached images (default behaviour)"
  echo "  -C           Use cached images"
  echo "  -d           Dryrun, print podman commands but don't execute"
  echo "  -r           Remove container image after build"
  echo
  echo "Targets:"
  echo "  Specify the target container image to build or push"
  echo "  If no target is specified, all container images will be processed"
  echo
  echo "Destination Registry:"
  echo "  Override the target registry path by setting the env var REGISTRY_PATH"
  echo "  default - quay.io/ramalama"
  echo
  echo "Examples:"
  echo "  Build CPU only image without cache:"
  echo "    $(basename "$0") build ramalama"
  echo
  echo "  Build CPU only image WITH cache:"
  echo "    $(basename "$0") build -C ramalama"
  echo
  echo "  Build CUDA image without cache:"
  echo "    $(basename "$0") build cuda"
  echo
  echo "  Build CUDA image WITH cache:"
  echo "    $(basename "$0") build -C cuda"
  echo
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
  local build_all=1
  local rm_after_build="false"
  local ci="false"
  local version=""
  local nocache="--no-cache"
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
    build "$target" "$command" "${version}"
  fi
}

REGISTRY_PATH=${REGISTRY_PATH:-quay.io/ramalama}
main "$@"
