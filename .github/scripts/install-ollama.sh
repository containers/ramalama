#!/usr/bin/env bash

set -eux -o pipefail

os_name=$(uname)

if [[ "$os_name" == "Darwin" ]]; then
  brew install ollama
  brew update
  brew services start ollama
elif [[ "$os_name" == "Linux" ]]; then
  ARCH=$(uname -m)
  case "$ARCH" in
    x86_64)
      ARCH=amd64
      ;;
    aarch64)
      ARCH=arm64
      ;;
  esac
  TARBALL=ollama-linux-$ARCH.tar.zst
  curl -fsSLO "https://ollama.com/download/$TARBALL"
  sudo tar -C /usr -xf "$TARBALL"
  sudo useradd -r -s /bin/false -U -m -d /usr/share/ollama ollama
  sudo usermod -a -G ollama "$(whoami)"
  rm "$TARBALL"
else
  echo "Operating system is neither macOS nor Linux"
  exit 1
fi
