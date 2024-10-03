#!/bin/bash

main() {
  set -e -o pipefail
  local rootdirs=("/opt/homebrew" "/usr/local" "/usr" "")
  local rootdir
  for rootdir in "${rootdirs[@]}"; do
    rm -rf "$rootdir/bin/ramalama" "$rootdir/share/ramalama"
  done
}

main "$@"

