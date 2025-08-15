#!/bin/bash

set_env() {
    # Work around compile errors introduced by gcc 15 no longer auto-importing cstdint
    export CXXFLAGS="-include cstdint"
    # pytorch on ppc64le does not support multi-version integration
    export USE_FFMPEG=0
}

build_pytorch() {
    local url="https://github.com/pytorch/pytorch.git"
    local version="v2.7.1"
    local commit
    commit=$(git ls-remote --tags "$url" "refs/tags/$version" | cut -f1)
    git_clone_specific_commit "$url" "$commit"
    # Update sleef to 3.8 to fix compilation errors with gcc 15 on PowerPC
    # See https://github.com/shibatch/sleef/issues/611 for more info
    pushd third_party/sleef
    git checkout refs/tags/3.8
    popd
    uv pip install -r requirements.txt
    uv pip install -v --no-build-isolation .
    cd ..
}

build_torchaudio() {
    local url="https://github.com/pytorch/audio.git"
    local version="v2.7.1"
    local commit
    commit=$(git ls-remote --tags "$url" "refs/tags/$version" | cut -f1)
    git_clone_specific_commit "$url" "$commit"
    uv pip install -v --no-build-isolation .
    cd ..
}

build_torchvision() {
    # Install built-time dependencies for pillow
    dnf -y --setopt=install_weak_deps=false install \
        zlib-devel libjpeg-devel openjpeg-devel libpng-devel libwebp-devel ffmpeg-free

    # The pytorch build forces installation of an older version of setuptools,
    # update to the latest to parse the pyproject.toml from pillow correctly
    uv pip install --upgrade setuptools

    local url="https://github.com/pytorch/vision.git"
    local version="v0.22.0"
    local commit
    commit=$(git ls-remote --tags "$url" "refs/tags/$version" | cut -f1)
    git_clone_specific_commit "$url" "$commit"
    uv pip install -v --no-build-isolation .
    cd ..
}

main() {
    set -eux -o pipefail

    local scriptdir
    scriptdir=$(dirname "$0")
    # shellcheck source=container-images/scripts/lib.sh
    source "$scriptdir/lib.sh"

    set_env

    build_pytorch

    if [ "$(uname -m)" == "ppc64le" ]; then
        build_torchaudio
        build_torchvision
    fi
}

main "@"
