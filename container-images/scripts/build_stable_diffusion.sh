#!/bin/bash

dnf_install() {
  local rpm_exclude_list="selinux-policy,container-selinux"
  local rpm_list=("gcc-c++" "cmake" "git-core")
  dnf install -y --setopt=install_weak_deps=false "${rpm_list[@]}" --exclude "${rpm_exclude_list}"
  dnf -y clean all
}

cmake_check_warnings() {
  awk -v rc=0 '/CMake Warning:/ { rc=1 } 1; END {exit rc}'
}

cmake_steps() {
  # This makes ggml build a generic binary, similar to an rpm build
  SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct)
  export SOURCE_DATE_EPOCH
  cmake -B build "$@" 2>&1 | cmake_check_warnings
  cmake --build build --config Release -j"$(nproc)" 2>&1 | cmake_check_warnings
  cmake --install build 2>&1 | cmake_check_warnings
}

clone_and_build_stable_diffusion_cpp() {
  # Using the correct leejet/stable-diffusion.cpp repository
  git clone --depth=1 https://github.com/leejet/stable-diffusion.cpp
  cd stable-diffusion.cpp
  git submodule update --init --recursive
  # Use master branch (latest stable)
  cmake_steps "${common_flags[@]}"

  cd ..
  rm -rf stable-diffusion.cpp
}

main() {
  # shellcheck disable=SC1091
  source /etc/os-release

  set -eux -o pipefail

  dnf_install

  local common_flags
  common_flags=(
    "-DGGML_STABLE_DIFFUSION=ON" "-DGGML_NATIVE=OFF" "-DGGML_CCACHE=OFF"
    "-DGGML_CMAKE_BUILD_TYPE=Release" "-DCMAKE_INSTALL_PREFIX=/usr"
  )

  # Build stable diffusion only (no whisper)
  clone_and_build_stable_diffusion_cpp
}

main "$@"
