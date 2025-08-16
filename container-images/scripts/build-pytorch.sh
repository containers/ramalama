#!/bin/bash

set_env() {
  export CMAKE_INSTALL_PREFIX="/usr"
  # Work around compile errors introduced by gcc 15 no longer auto-imports cstdint
  export CXXFLAGS="-include cstdint"
}

main() {
  set -eux -o pipefail

  repo="https://github.com/pytorch/pytorch.git"
  version="v2.7.0"
  commit=$(git ls-remote --tags "$repo" "refs/tags/$version" | cut -f1)

  git config set --global advice.defaultBranchName false
  git init pytorch
  cd pytorch
  git remote add origin "$repo"
  git fetch --depth 1 origin "$commit"
  git reset --hard "$commit"
  git submodule update --init --recursive

  set_env
  pip install -r requirements.txt
  python3 -m pip install --no-build-isolation -v .
}

main "@"
