#!/bin/bash

cleanup() {
  rm -rf "$TMP" &
}

available() {
  command -v $1 >/dev/null
}

main() {
  set -e -o pipefail

  if [ "$(uname -s)" != "Linux" ]; then
    echo "This script is intended to run on Linux only"
    return 1
  fi

  if [ "$EUID" -ne 0 ]; then
    echo "This script is intended to run as root only"
    return 2
  fi

  local bindir
  for bindir in /usr/local/bin /usr/bin /bin; do
    echo $PATH | grep -q $bindir && break || continue
  done

  TMP="$(mktemp -d)"
  trap cleanup EXIT
  local from="podman-llm"
  local url="raw.githubusercontent.com/ericcurtin/podman-llm/main/$FROM"
  local from="$TMP/$from"
  curl -fsSL -o "$from" "https://$url"
  install -D -m755 "$from" "$bindir/"
}

main "$@"

