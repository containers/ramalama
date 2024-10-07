#!/bin/bash

available() {
  command -v "$1" >/dev/null
}

main() {
  set -e -o pipefail
  local rootdirs=("/opt/homebrew" "/usr/local" "/usr" "")
  local rootdir
  for rootdir in "${rootdirs[@]}"; do
    rm -rf "$rootdir/bin/ramalama" "$rootdir/share/ramalama"
  done

  if available pipx; then
    pipx uninstall ramalama
  fi
}

main "$@"

