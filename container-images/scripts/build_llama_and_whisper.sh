#!/bin/bash

dnf_install() {
  local rpm_list=("python3" "python3-pip" "python3-argcomplete" \
                  "python3-dnf-plugin-versionlock" "gcc-c++" "cmake" "vim" \
                  "procps-ng" "git" "dnf-plugins-core")
  local vulkan_rpms=("vulkan-headers" "vulkan-loader-devel" "vulkan-tools" \
                     "spirv-tools" "glslc" "glslang")
  if [ "$containerfile" = "ramalama" ]; then
    local url="https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm"
    dnf install -y "$url"
    crb enable
    dnf install -y epel-release
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
    dnf install -y mesa-vulkan-drivers-23.3.3-102.el9 "${vulkan_rpms[@]}"
  elif [ "$containerfile" = "asahi" ]; then
    dnf copr enable -y @asahi/fedora-remix-branding
    dnf install -y asahi-repos
    dnf install -y mesa-vulkan-drivers "${vulkan_rpms[@]}" "${rpm_list[@]}"
  elif [ "$containerfile" = "rocm" ]; then
    dnf install -y rocm-dev hipblas-devel rocblas-devel
  elif [ "$containerfile" = "cuda" ]; then
    dnf install -y "${rpm_list[@]}"
  fi

  # For Vulkan image, we don't need to install anything extra but rebuild with
  # -DGGML_VULKAN
}

cmake_steps() {
  local flag="$1"
  cmake -B build "${common_flags[@]}" "$flag"
  cmake --build build --config Release -j"$(nproc)"
  cmake --install build
}

main() {
  set -e

  local containerfile="$1"
  local llama_cpp_sha="$2"
  local whisper_cpp_sha="$3"
  local install_prefix="$4"
  local build_flag_1="$5"
  local build_flag_2="$6"
  local common_flags=("-DGGML_CCACHE=0" \
                      "-DCMAKE_INSTALL_PREFIX=$install_prefix" "$build_flag_1")
  if [ -n "$build_flag_2" ]; then
    common_flags+=("$build_flag_2")
  fi

  dnf_install

  git clone https://github.com/ggerganov/llama.cpp
  cd llama.cpp
  git reset --hard "$llama_cpp_sha"
  cmake_steps
  cd ..

  git clone https://github.com/ggerganov/whisper.cpp
  cd whisper.cpp
  git reset --hard "$whisper_cpp_sha"
  cmake_steps "-DBUILD_SHARED_LIBS=NO"
  mv build/bin/main "$install_prefix/bin/whisper-main"
  mv build/bin/server "$install_prefix/bin/whisper-server"
  cd ..

  CMAKE_ARGS="${common_flags[*]}" FORCE_CMAKE=1 \
    pip install --prefix="$install_prefix" 'llama-cpp-python[server]'

  dnf clean all
  rm -rf /var/cache/*dnf* /opt/rocm-*/lib/llvm \
    /opt/rocm-*/lib/rocblas/library/*gfx9* llama.cpp whisper.cpp
}

main "$@"

