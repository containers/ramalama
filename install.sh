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
  local curl_cmd=("curl" "--globoff" "--location" "--proto-default" "https")
  curl_cmd+=("-o" "$from" "--remote-time" "--retry" "10" "--retry-max-time")
  curl_cmd+=("10" "https://$url")
  "${curl_cmd[@]}"
}

main() {
  set -e -o pipefail

  local os
  os="$(uname -s)"
  if [ "$os" != "Linux" ]; then
    echo "This script is intended to run on Linux only"
    return 1
  fi

  if [ "$EUID" -ne 0 ]; then
    echo "This script is intended to run as root only"
    return 2
  fi

  local bindir
  for bindir in /usr/local/bin /usr/bin /bin; do
    if echo "$PATH" | grep -q $bindir; then
      break
    fi
  done

  TMP="$(mktemp -d)"
  trap cleanup EXIT
  local from="ramalama"
  local url="raw.githubusercontent.com/containers/ramalama/s/$from"
  local from="$TMP/$from"
  download

  # only for macOS for now, which doesn't have containers
  if [ "$os" != "Linux" ]; then
    pip install "huggingface_hub[cli]==0.24.2"
    pip install "omlmd"
  fi

  install -D -m755 "$from" "$bindir/"

  if false; then # to be done
    gpu_check
  fi
}

main "$@"

