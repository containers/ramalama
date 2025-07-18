#!/bin/bash

available() {
  command -v "$1" >/dev/null
}

install_deps() {
  set -eux -o pipefail

  if available dnf; then
    dnf install -y git curl wget ca-certificates gcc gcc-c++ \
      gperftools-libs numactl-devel ffmpeg libSM libXext mesa-libGL jq lsof \
      vim numactl
    dnf -y clean all
    rm -rf /var/cache/*dnf*
  elif available apt-get; then
    apt-get update -y
    apt-get install -y --no-install-recommends git curl wget ca-certificates \
      gcc g++ libtcmalloc-minimal4 libnuma-dev ffmpeg libsm6 libxext6 libgl1 \
      jq lsof vim numactl
    rm -rf /var/lib/apt/lists/*
  fi

  curl -LsSf https://astral.sh/uv/0.7.21/install.sh | bash
}

preload_and_ulimit() {
  local ld_preload_file="libtcmalloc_minimal.so.4"
  local ld_preload_file_1="/usr/lib/$arch-linux-gnu/$ld_preload_file"
  local ld_preload_file_2="/usr/lib64/$ld_preload_file"
  if [ -e "$ld_preload_file_1" ]; then
    ld_preload_file="$ld_preload_file_1"
  elif [ -e "$ld_preload_file_2" ]; then
    ld_preload_file="$ld_preload_file_2"
  fi

  if [ -e "$ld_preload_file" ]; then
    echo "LD_PRELOAD=$ld_preload_file" >> /etc/environment
  fi

  echo 'ulimit -c 0' >> ~/.bashrc
}

pip_install() {
  local url="https://download.pytorch.org/whl/cpu"
  uv pip install -v -r "$1" --extra-index-url $url
}

git_clone_specific_commit() {
  local repo="${vllm_url##*/}"
  git init "$repo"
  cd "$repo"
  git remote add origin "$vllm_url"
  git fetch --depth 1 origin $commit
  git reset --hard $commit
}

main() {
  set -eux -o pipefail

  install_deps

  local arch
  arch=$(uname -m)
  preload_and_ulimit

  uv venv --python 3.12 --seed "$VIRTUAL_ENV"
  uv pip install --upgrade pip

  local vllm_url="https://github.com/vllm-project/vllm"
  local commit="ac9fb732a5c0b8e671f8c91be8b40148282bb14a"
  git_clone_specific_commit
  if [ "$arch" == "x86_64" ]; then
    export VLLM_CPU_DISABLE_AVX512="0"
    export VLLM_CPU_AVX512BF16="0"
    export VLLM_CPU_AVX512VNNI="0"
  elif [ "$arch" == "aarch64" ]; then
    export VLLM_CPU_DISABLE_AVX512="true"
  fi

  pip_install requirements/cpu-build.txt
  pip_install requirements/cpu.txt

  MAX_JOBS=2 VLLM_TARGET_DEVICE=cpu python3 setup.py install
  cd -
  rm -rf vllm /root/.cache
}

main "$@"

