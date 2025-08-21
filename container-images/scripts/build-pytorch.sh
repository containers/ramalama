#!/bin/bash

set_env() {
  # Work around compile errors introduced by gcc 15 no longer auto-importing cstdint
  export CXXFLAGS="-include cstdint"
  # ppc64le does not support multi-version integration
  export USE_FFMPEG=0
}

clone_at_tag() {
  local url="$1"
  local version="$2"
  local commit
  commit=$(git ls-remote --tags "$url" "refs/tags/$version" | cut -f1)
  local repo="${url##*/}"
  repo="${repo%.git}"

  git init "$repo"
  pushd "$repo"
  git remote add origin "$url"
  git fetch --depth 1 origin "$commit"
  git reset --hard "$commit"
  git submodule update --init --recursive
  popd
}

main() {
  set -eux -o pipefail

  git config set --global advice.defaultBranchName false

  clone_at_tag https://github.com/pytorch/pytorch.git v2.7.1
  # Update sleef to 3.8 to fix compilation errors with gcc 15 on PowerPC
  # See https://github.com/shibatch/sleef/issues/611 for more info
  pushd pytorch/third_party/sleef
  git checkout refs/tags/3.8
  popd
  set_env
  uv pip install -r pytorch/requirements.txt
  uv pip install -v --no-build-isolation ./pytorch

  if [ "$(uname -m)" == "ppc64le" ]; then
    clone_at_tag https://github.com/pytorch/audio.git v2.7.1
    uv pip install -v --no-build-isolation ./audio

    # Install built-time dependencies for pillow
    dnf -y --setopt=install_weak_deps=false install \
      zlib-devel libjpeg-devel openjpeg-devel libpng-devel libwebp-devel ffmpeg-free
    # pytorch requires an older version of setuptools, update to the latest to
    # parse the pyproject.toml from pillow correctly
    uv pip install --upgrade setuptools

    clone_at_tag https://github.com/pytorch/vision.git v0.22.0
    uv pip install -v --no-build-isolation ./vision
  fi
}

main "@"
