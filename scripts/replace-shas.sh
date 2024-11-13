#!/bin/bash

set -euo pipefail

find_files() {
  grep -rl "$1_CPP_SHA=" container-images/
}

sed_files() {
  xargs sed -i "s/ARG $1_CPP_SHA=.*/ARG $1_CPP_SHA=$2/g"
}

find_files "LLAMA" | sed_files "LLAMA" "$1"
find_files "WHISPER" | sed_files "WHISPER" "$2"

