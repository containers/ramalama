#!/usr/bin/env bash

os_name=$(uname)

if [[ "$os_name" == "Darwin" ]]; then
  brew install ollama
  brew services start ollama
elif [[ "$os_name" == "Linux" ]]; then
  curl -L https://ollama.com/download/ollama-linux-amd64.tgz -o ollama-linux-amd64.tgz
  sudo tar -C /usr -xzf ollama-linux-amd64.tgz
  sudo useradd -r -s /bin/false -U -m -d /usr/share/ollama ollama
  sudo usermod -a -G ollama $(whoami)
else
  echo "Operating system is neither macOS nor Linux"
fi