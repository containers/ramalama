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
  curl --globoff --location --proto-default https -f -o "$2" \
      --remote-time --retry 10 --retry-max-time 10 -s "$1"
  local bn="$(basename "$1")"
  echo "Downloaded $bn"
}

apt_get_install() {
  apt-get -qq -y install "$1"
}

check_platform() {
  if [ "$os" = "Darwin" ]; then
    if [ "$EUID" -eq 0 ]; then
      echo "This script is intended to run as non-root on macOS"
      return 1
    fi

    if ! available "brew"; then
      echo "RamaLama requires brew to complete installation. Install brew and add the"
      echo "directory containing brew to the PATH before continuing to install RamaLama"
      return 2
    fi
  elif [ "$os" = "Linux" ]; then
    if [ "$EUID" -ne 0 ]; then
      if ! available sudo; then
        error "This script is intended to run as root on Linux"
        return 3
      fi

      sudo="sudo"
    fi

    if available dnf; then
      $sudo dnf install -y --best podman || true
    elif available apt-get; then
      $sudo apt-get update -qq || true
      $sudo apt_get_install podman || $sudo apt_get_install docker || true
    fi
  else
    echo "This script is intended to run on Linux and macOS only"
    return 4
  fi

  return 0
}

install_mac_dependencies() {
  brew install llama.cpp
}

setup_ramalama() {
  local binfile="ramalama"
  local from_file="${binfile}"
  local host="https://raw.githubusercontent.com"
  local branch="${BRANCH:-s}"
  local url="${host}/containers/ramalama/${branch}/bin/${from_file}"
  local to_file="${2}/${from_file}"

  if [ "$os" == "Darwin" ]; then
    install_mac_dependencies
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
                      "file.py" "http_client.py" "url.py" "annotations.py")

  for i in "${python_files[@]}"; do
    url="${host}/containers/ramalama/${branch}/ramalama/${i}"
    download "$url" "$to_file"
    $sudo install -m755 "$to_file" "${syspath}/${i}"
  done
}

main() {
  set -e -o pipefail
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

  setup_ramalama "$bindir" "$TMP"
}

main "$@"

