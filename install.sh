#!/bin/bash

cleanup() {
  rm -rf "$TMP" &
}

available() {
  command -v "$1" >/dev/null
}

nvidia_lshw() {
  lshw -c display -numeric -disable network | grep -q 'vendor: .* \[10DE\]'
}

amd_lshw() {
  lshw -c display -numeric -disable network | grep -q 'vendor: .* \[1002\]'
}

download() {
  if $local_install; then
    cp "$1" "$2"
  else
    curl --globoff --location --proto-default https -f -o "$2" \
        --remote-time --retry 10 --retry-max-time 10 -s -S "$1"
  fi

  echo -n "█"
}

dnf_install() {
  $sudo dnf install -y "$1"
}

dnf_install_podman() {
  if ! available podman; then
    dnf_install podman || true
  fi
}

apt_install() {
  apt install -y "$1"
}

apt_update_install() {
  if ! available podman; then
    $sudo apt update || true

    # only install docker if podman can't be
    if ! $sudo apt_install podman; then
      if ! available docker; then
        $sudo apt_install docker || true
      fi
    fi
  fi
}

install_mac_dependencies() {
  if [ "$EUID" -eq 0 ]; then
    echo "This script is intended to run as non-root on macOS"

    return 1
  fi

  if ! available "brew"; then
    echo "RamaLama requires brew to complete installation. Install brew and add the"
    echo "directory containing brew to the PATH before continuing to install RamaLama"

    return 2
  fi

  brew install llama.cpp
}

check_platform() {
  if $local_install; then
    return 0
  fi

  if [ "$os" = "Darwin" ]; then
    install_mac_dependencies
  elif [ "$os" = "Linux" ]; then
    if [ "$EUID" -ne 0 ]; then
      if ! available sudo; then
        error "This script is intended to run as root on Linux"

        return 3
      fi

      sudo="sudo"
    fi

    if available dnf && ! grep -q ostree= /proc/cmdline; then
      dnf_install_podman
    elif available apt; then
      apt_update_install
    fi
  else
    echo "This script is intended to run on Linux and macOS only"

    return 4
  fi

  return 0
}

get_sysdir() {
  local bindirs=("/opt/homebrew/bin" "/usr/local/bin" "/usr/bin")
  local bindir
  for bindir in "${bindirs[@]}"; do
    if echo "$PATH" | grep -q "$bindir"; then
      break
    fi
  done

  sysdir="$(dirname "$bindir")"
}

setup_ramalama() {
  local binfile="ramalama"
  local from_file="${binfile}"
  local host="https://raw.githubusercontent.com"
  local branch="${BRANCH:-s}"
  local url="${host}/containers/ramalama/${branch}/bin/${from_file}"
  local to_file="$TMP/${from_file}"
  local sysdir
  get_sysdir

  if $local_install; then
    url="bin/${from_file}"
  fi

  download "$url" "$to_file"
  local max_jobs
  max_jobs="$(getconf _NPROCESSORS_ONLN)"
  install_ramalama_bin
  install_ramalama_libs
  install_ramalama_libexecs
  echo
}

install_ramalama_bin() {
  $sudo install -m755 "$to_file" "$sysdir/bin/ramalama"
}

install_dirs() {
  local dir="$1"
  $sudo install -m755 -d "$dir"
  dir="$dir/ramalama"
  $sudo install -m755 -d "$dir"
}

download_install() {
  local url_dir="$1"
  local dir="$2"
  local file="$3"
  if $local_install; then
    url="$url_dir/$file"
  else
    url="$host/containers/ramalama/$branch/$url_dir/$file"
  fi

  mkdir -p "$TMP/$dir"
  download "$url" "$TMP/$dir/$file"
  $sudo install -m755 "$TMP/$dir/$file" "$sysdir/$dir/$file"
}

install_ramalama_libs() {
  local sharedir="$sysdir/share/ramalama"
  install_dirs "$sharedir"
  local python_files=("cli.py" "config.py" "rag.py" "gguf_parser.py" \
                      "huggingface.py" "model.py" "model_factory.py" \
                      "model_store.py" "model_inspect.py" "ollama.py" \
                      "common.py" "__init__.py" "quadlet.py" "kube.py" \
                      "oci.py" "version.py" "shortnames.py" "toml_parser.py" \
                      "file.py" "http_client.py" "url.py" "annotations.py" \
                      "gpu_detector.py" "console.py")
  local job_count=0
  local job_queue=()
  for i in "${python_files[@]}"; do
    download_install "ramalama" "share/ramalama/ramalama" "$i" &
    job_queue+=($!)
    ((++job_count))

    if ((job_count > max_jobs)); then
      wait "${job_queue[0]}"
      job_queue=("${job_queue[@]:1}")
      ((--job_count))
    fi
  done

  # Wait for remaining jobs to finish
  wait

}

install_ramalama_libexecs() {
  local python_files=("client" "serve" "run")
  local libexecdir="$sysdir/libexec"
  install_dirs "$libexecdir"
  local job_count=0
  local job_queue=()
  for i in "${python_files[@]}"; do
    download_install "libexec" "libexec" "ramalama-$i-core" &
    job_queue+=($!)
    ((++job_count))

    if ((job_count > max_jobs)); then
      wait "${job_queue[0]}"
      job_queue=("${job_queue[@]:1}")
      ((--job_count))
    fi
  done

  # Wait for remaining jobs to finish
  wait
}

parse_arguments() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -l)
        local_install="true"
        shift
        ;;
      *)
        break
    esac
  done
}

main() {
  set -e -o pipefail

  local local_install="false"
  parse_arguments "$@"

  local os
  os="$(uname -s)"
  local sudo=""
  check_platform
  if ! $local_install && [ -z "$BRANCH" ] && available dnf && \
       dnf_install "python3-ramalama"; then
    return 0
  fi

  TMP="$(mktemp -d)"
  trap cleanup EXIT

  setup_ramalama
}

main "$@"
