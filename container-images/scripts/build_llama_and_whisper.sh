#!/bin/bash

dnf_install() {
  local rpm_list=("python3" "python3-pip" "python3-argcomplete" \
                  "python3-dnf-plugin-versionlock" "gcc-c++" "cmake" "vim" \
                  "procps-ng" "git" "dnf-plugins-core" "libcurl-devel")
  local vulkan_rpms=("vulkan-headers" "vulkan-loader-devel" "vulkan-tools" \
                     "spirv-tools" "glslc" "glslang")

  # All the UBI-based ones
  if [ "$containerfile" = "ramalama" ] || [ "$containerfile" = "rocm" ] || \
    [ "$containerfile" = "vulkan" ]; then
    local url="https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm"
    dnf install -y "$url"
    crb enable # this is in epel-release, can only install epel-release via url
    dnf --enablerepo=ubi-9-appstream-rpms install -y "${rpm_list[@]}"
    local uname_m
    uname_m="$(uname -m)"
    dnf copr enable -y slp/mesa-krunkit "epel-9-$uname_m"
    url="https://mirror.stream.centos.org/9-stream/AppStream/$uname_m/os/"
    dnf config-manager --add-repo "$url"
    url="http://mirror.centos.org/centos/RPM-GPG-KEY-CentOS-Official"
    curl --retry 8 --retry-all-errors -o \
      /etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-Official "$url"
    rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-Official
    dnf install -y mesa-vulkan-drivers "${vulkan_rpms[@]}"
  fi

  if [ "$containerfile" = "asahi" ]; then
    dnf copr enable -y @asahi/fedora-remix-branding
    dnf install -y asahi-repos
    dnf install -y mesa-vulkan-drivers "${vulkan_rpms[@]}" "${rpm_list[@]}"
  elif [ "$containerfile" = "rocm" ]; then
    dnf install -y rocm-dev hipblas-devel rocblas-devel
  elif [ "$containerfile" = "cuda" ]; then
    dnf install -y "${rpm_list[@]}" gcc-toolset-12
    # shellcheck disable=SC1091
    . /opt/rh/gcc-toolset-12/enable
  fi
}

cmake_check_warnings() {
  awk -v rc=0 '/CMake Warning:/ { rc=1 } 1; END {exit rc}'
}

cmake_steps() {
  local cmake_flags=("$@")
  cmake -B build "${cmake_flags[@]}" 2>&1 | cmake_check_warnings
  cmake --build build --config Release -j"$(nproc)" 2>&1 | cmake_check_warnings
  cmake --install build 2>&1 | cmake_check_warnings
}

set_install_prefix() {
  if [ "$containerfile" = "cuda" ]; then
    install_prefix="/tmp/install"
  else
    install_prefix="/usr"
  fi
}

configure_common_flags() {
  common_flags=("-DGGML_NATIVE=OFF")
  case "$containerfile" in
    rocm)
      common_flags+=("-DGGML_HIP=ON" "-DAMDGPU_TARGETS=${AMDGPU_TARGETS:-gfx1010,gfx1030,gfx1032,gfx1100,gfx1101,gfx1102}")
      ;;
    cuda)
      common_flags+=("-DGGML_CUDA=ON" "-DCMAKE_EXE_LINKER_FLAGS=-Wl,--allow-shlib-undefined")
      ;;
    vulkan | asahi)
      common_flags+=("-DGGML_VULKAN=1")
      ;;
  esac
}

clone_and_build_whisper_cpp() {
  local whisper_flags=("${common_flags[@]}")
  local whisper_cpp_sha="8a9ad7844d6e2a10cddf4b92de4089d7ac2b14a9"
  whisper_flags+=("-DBUILD_SHARED_LIBS=NO")

  git clone https://github.com/ggerganov/whisper.cpp
  cd whisper.cpp
  git submodule update --init --recursive
  git reset --hard "$whisper_cpp_sha"
  cmake_steps "${whisper_flags[@]}"
  mkdir -p "$install_prefix/bin"
  cd ..
  rm -rf whisper.cpp
}

clone_and_build_llama_cpp() {
  local llama_cpp_sha="acd38efee316f3a5ed2e6afcbc5814807c347053"

  git clone https://github.com/ggerganov/llama.cpp
  cd llama.cpp
  git submodule update --init --recursive
  git reset --hard "$llama_cpp_sha"
  cmake_steps "${common_flags[@]}"
  cd ..
  rm -rf llama.cpp
}

main() {
  set -ex

  local containerfile="$1"
  local install_prefix
  set_install_prefix
  local common_flags
  configure_common_flags
  common_flags+=("-DGGML_CCACHE=OFF" "-DCMAKE_INSTALL_PREFIX=$install_prefix")
  dnf_install
  clone_and_build_whisper_cpp
  common_flags+=("-DLLAMA_CURL=ON")
  case "$containerfile" in
    ramalama)
      common_flags+=("-DGGML_KOMPUTE=ON" "-DKOMPUTE_OPT_DISABLE_VULKAN_VERSION_CHECK=ON")
      ;;
  esac

  clone_and_build_llama_cpp
  dnf -y clean all
  rm -rf /var/cache/*dnf* /opt/rocm-*/lib/*/library/*gfx9*
  ldconfig # needed for libraries
}

main "$@"
