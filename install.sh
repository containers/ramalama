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
        --remote-time --retry 10 --retry-max-time 10 -s "$1"
    local bn
    bn="$(basename "$1")"
    echo "Downloaded $bn"
  fi
}

dnf_install() {
  if ! available podman; then
    $sudo dnf install -y --best podman || true
  fi
}

apt_get_install() {
  apt-get -y install "$1"
}

apt_install() {
  if ! available podman; then
    $sudo apt-get update || true

    # only install docker if podman can't be
    if ! $sudo apt_get_install podman; then
      if ! available docker; then
        $sudo apt_get_install docker || true
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
      dnf_install
    elif available apt-get; then
      apt_install
    fi
  else
    echo "This script is intended to run on Linux and macOS only"

    return 4
  fi

  return 0
}

setup_version_file() {
  local config_dir="$HOME/.config/ramalama"
  local version_file="$config_dir/version"

  # Ensure ~/.config/ramalama/ exists
  mkdir -p "$config_dir"

  version="0.0.0"
  # Try to get version from Git
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    version=$(git describe --tags --long --always)
    # Format version properly (strip 'g' from commit hash)
    if [[ "$version" =~ ([0-9]+\.[0-9]+\.[0-9]+)-([0-9]+)-g([a-f0-9]+) ]]; then
      version="${BASH_REMATCH[1]}.dev${BASH_REMATCH[2]}+${BASH_REMATCH[3]}"
    fi
  fi

  # Save version to file
  echo "$version" > "$version_file"

  echo "Saved version: $version in $version_file"
}

setup_ramalama() {
  local binfile="ramalama"
  local from_file="${binfile}"
  local host="https://raw.githubusercontent.com"
  local branch="${BRANCH:-s}"
  local url="${host}/containers/ramalama/${branch}/bin/${from_file}"
  local to_file="$TMP/${from_file}"
  if $local_install; then
    url="bin/${from_file}"
  fi

  download "$url" "$to_file"
  local ramalama_bin="${1}/${binfile}"
  local sharedirs=("/opt/homebrew/share" "/usr/local/share" "/usr/share")
  local syspath
  for dir in "${sharedirs[@]}"; do
    if [ -d "$dir" ]; then
      syspath="$dir/ramalama"
      break
    fi
  done

  $sudo install -m755 -d "$syspath"
  syspath="$syspath/ramalama"
  $sudo install -m755 -d "$syspath"
  $sudo install -m755 "$to_file" "$ramalama_bin"
  local python_files=("cli.py" "huggingface.py" "model.py" "ollama.py" \
                      "common.py" "__init__.py" "quadlet.py" "kube.py" \
                      "oci.py" "version.py" "shortnames.py" "toml_parser.py" \
                      "file.py" "http_client.py" "url.py" "annotations.py" \
                      "gpu_detector.py" "console.py")
  for i in "${python_files[@]}"; do
    if $local_install; then
      url="ramalama/${i}"
    else
      url="${host}/containers/ramalama/${branch}/ramalama/${i}"
    fi

    download "$url" "$to_file"
    $sudo install -m755 "$to_file" "${syspath}/${i}"
  done
}

main() {
  set -e -o pipefail

  local local_install="false"
  # Parse command line arguments
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

  local os
  os="$(uname -s)"
  local sudo=""
  check_platform

  local bindirs=("/opt/homebrew/bin" "/usr/local/bin" "/usr/bin" "/bin")
  local bindir
  for bindir in "${bindirs[@]}"; do
    if echo "$PATH" | grep -q "$bindir"; then
      break
    fi
  done

  if [ -z "$bindir" ]; then
    echo "No suitable bindir found in PATH"
    exit 5
  fi

  TMP="$(mktemp -d)"
  trap cleanup EXIT

  setup_ramalama "$bindir"
  setup_version_file
}

main "$@"
