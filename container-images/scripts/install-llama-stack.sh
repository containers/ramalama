#!/bin/bash

DNF_CMD="dnf -y --setopt=install_weak_deps=false"

conan_build_cmake() {
    git clone --depth=1 https://github.com/conan-io/conan-center-index.git
    # These builds complain about the conan cmake version, so build them first using the system cmake
    for i in bzip2/1.0.8 double-conversion/3.2.1 gflags/2.2.2 lz4/1.9.4; do
        name="${i%/*}"
        version="${i#*/}"
        echo "Building $name $version with conan"
        # Remove conan version requirement
        sed -i -e '/required_conan_version/d' "conan-center-index/recipes/$name/all/conanfile.py"
        conan create -o "${name}:shared=True" --build=missing \
              "conan-center-index/recipes/$name/all" "${version}@"
    done
    yq -i '
      .sources."3.30.5" = {
        "url": "https://github.com/Kitware/CMake/releases/download/v3.30.5/cmake-3.30.5.tar.gz",
        "sha256": "9f55e1a40508f2f29b7e065fa08c29f82c402fa0402da839fffe64a25755a86d"
      }' conan-center-index/recipes/cmake/3.x.x/conandata.yml
    conan create -o cmake:bootstrap=True -o cmake:with_openssl=False --build=missing \
          conan-center-index/recipes/cmake/3.x.x 3.30.5@
}

build_milvus_lite() {
    # shellcheck source=container-images/scripts/lib.sh
    source "$scriptdir/lib.sh"

    local url="https://github.com/milvus-io/milvus-lite.git"
    local version="v2.5.1"
    local commit
    commit=$(git ls-remote --tags "$url" "refs/tags/$version" | cut -f1)
    git_clone_specific_commit "$url" "$commit"
    conan config init
    # Add gcc 15 as a supported compiler in the default settings
    sed -i -e 's/"14.1"/"14.1", "15"/' ~/.conan/settings.yml
    conan profile update settings.compiler.libcxx=libstdc++11 default
    # Work around compile errors introduced by gcc 15 no longer auto-importing cstdint
    export CXXFLAGS="-include cstdint"
    # One of the dependencies requires cmake 3.30.5 specifically, so
    # it needs to be built from source
    conan_build_cmake
    mkdir -p ~/.cargo/bin
    # Add openblas include dir for knowhere build
    sed -i -e '/BuildUtils.cmake/ a include_directories("/usr/include/openblas")' CMakeLists.txt
    uv pip install -v ./python
    rm -rf ~/.cache ~/.cargo ~/.cmake ~/.conan
    cd ..
}

build_deps() {
    "$scriptdir/build-pytorch.sh"
    build_milvus_lite
}

main() {
    set -eux -o pipefail

    local ramalama_stack_version="$1"
    if [ -z "$ramalama_stack_version" ]; then
        echo "$0: error: please provide the version of ramalama-stack to install"
        exit 1
    fi

    $DNF_CMD install uv cmake gcc gcc-c++ python3-devel pkg-config
    uv venv --seed "$VIRTUAL_ENV"
    # shellcheck disable=SC1091
    source "$VIRTUAL_ENV/bin/activate"

    if [ "$(uname -m)" == "ppc64le" ] || [ "$(uname -m)" == "s390x" ]; then
        $DNF_CMD install git-core yq rust cargo perl texinfo diffutils openblas-devel
        if [ "$(uname -m)" != "s390x" ]; then
            $DNF_CMD install libquadmath-devel
        fi
        git config set --global advice.defaultBranchName false
        uv pip install setuptools wheel "conan<2"
        local scriptdir
        scriptdir=$(dirname "$0")
        build_deps
    fi

    uv pip install -v "ramalama-stack==${ramalama_stack_version}"
    $DNF_CMD clean all
}

main "$@"
