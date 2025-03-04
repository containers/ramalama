#!/bin/bash

available() {
  command -v "$1" >/dev/null
}

dnf_install_intel_gpu() {
  local intel_rpms=("intel-oneapi-mkl-sycl-devel" "intel-oneapi-dnnl-devel" \
                  "intel-oneapi-compiler-dpcpp-cpp" "intel-level-zero" \
                  "oneapi-level-zero" "oneapi-level-zero-devel" "intel-compute-runtime")
  dnf install -y "${rpm_list[@]}" "${intel_rpms[@]}"

  # shellcheck disable=SC1091
  . /opt/intel/oneapi/setvars.sh
}

dnf_install() {
  local rpm_list=("podman-remote" "python3" "python3-pip" "python3-argcomplete" \
                  "python3-dnf-plugin-versionlock" "gcc-c++" "cmake" "vim" \
                  "procps-ng" "git" "dnf-plugins-core" "libcurl-devel" "gawk")
  local vulkan_rpms=("vulkan-headers" "vulkan-loader-devel" "vulkan-tools" \
                     "spirv-tools" "glslc" "glslang")
  if [[ "${containerfile}" = "ramalama" ]] || [[ "${containerfile}" =~ rocm* ]] || \
    [[ "${containerfile}" = "vulkan" ]]; then # All the UBI-based ones
    if [ "${ID}" = "fedora" ]; then
      dnf install -y "${rpm_list[@]}"
    else
      local url="https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm"
      dnf install -y "$url"
      crb enable # this is in epel-release, can only install epel-release via url
      dnf --enablerepo=ubi-9-appstream-rpms install -y "${rpm_list[@]}"
    fi
    # x86_64 and aarch64 means kompute
    if [ "$uname_m" = "x86_64" ] || [ "$uname_m" = "aarch64" ]; then
      if [[ "${ID}" == "rhel" || "${ID}" == "redhat" || "${ID}" == "centos" ]]; then
        dnf copr enable -y slp/mesa-krunkit "epel-9-$uname_m"
        url="https://mirror.stream.centos.org/9-stream/AppStream/$uname_m/os/"
        dnf config-manager --add-repo "$url"
        url="http://mirror.centos.org/centos/RPM-GPG-KEY-CentOS-Official"
        curl --retry 8 --retry-all-errors -o \
            /etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-Official "$url"
        rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-Official
      fi
      dnf install -y mesa-vulkan-drivers "${vulkan_rpms[@]}"
    else
      dnf install -y "openblas-devel"
    fi

    if [ "$containerfile" = "rocm" ]; then
      if [ "${ID}" = "fedora" ]; then
        dnf install -y rocm-core-devel hipblas-devel rocblas-devel rocm-hip-devel
      else
        dnf install -y rocm-dev hipblas-devel rocblas-devel
      fi
    fi
  elif [ "$containerfile" = "asahi" ]; then
    dnf copr enable -y @asahi/fedora-remix-branding
    dnf install -y asahi-repos
    dnf install -y mesa-vulkan-drivers "${vulkan_rpms[@]}" "${rpm_list[@]}"
  elif [ "$containerfile" = "cuda" ]; then
    dnf install -y "${rpm_list[@]}" gcc-toolset-12
    # shellcheck disable=SC1091
    . /opt/rh/gcc-toolset-12/enable
  elif [ "$containerfile" = "intel-gpu" ]; then
    dnf_install_intel_gpu
  fi

  dnf -y clean all
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
  if [ "$containerfile" = "cuda" ] || [ "$containerfile" = "intel-gpu" ]; then
    install_prefix="/tmp/install"
  else
    install_prefix="/usr"
  fi
}

configure_common_flags() {
  common_flags=("-DGGML_NATIVE=OFF")
  case "$containerfile" in
    rocm*)
      if [ "${ID}" = "fedora" ]; then
        common_flags+=("-DCMAKE_HIP_COMPILER_ROCM_ROOT=/usr")
      fi
      common_flags+=("-DGGML_HIP=ON" "-DAMDGPU_TARGETS=${AMDGPU_TARGETS:-gfx1010,gfx1012,gfx1030,gfx1032,gfx1100,gfx1101,gfx1102,gfx1103,gfx1151,gfx1200,gfx1201}")
      ;;
    cuda)
      common_flags+=("-DGGML_CUDA=ON" "-DCMAKE_EXE_LINKER_FLAGS=-Wl,--allow-shlib-undefined")
      ;;
    vulkan | asahi)
      common_flags+=("-DGGML_VULKAN=1")
      ;;
    intel-gpu)
      common_flags+=("-DGGML_SYCL=ON" "-DCMAKE_C_COMPILER=icx" "-DCMAKE_CXX_COMPILER=icpx")
      ;;
  esac
}

clone_and_build_whisper_cpp() {
  local whisper_flags=("${common_flags[@]}")
  local whisper_cpp_sha="d682e150908e10caa4c15883c633d7902d385237"
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
  local llama_cpp_sha="c43af9276b119dae7436b7878d59671d0f6b1a97"

  git clone https://github.com/ggml-org/llama.cpp
  cd llama.cpp
  git submodule update --init --recursive
  git reset --hard "$llama_cpp_sha"
  cmake_steps "${common_flags[@]}"
  cd ..
  rm -rf llama.cpp
}

clone_and_build_ramalama() {
  # link podman-remote to podman for use by RamaLama
  ln -sf /usr/bin/podman-remote /usr/bin/podman
  git clone https://github.com/containers/ramalama
  cd ramalama
  git submodule update --init --recursive
  pip install . --prefix=/usr
  cd ..
  rm -rf ramalama
}

main() {
  # shellcheck disable=SC1091
  source /etc/os-release

  set -ex

  local containerfile="$1"
  local install_prefix
  local uname_m
  uname_m="$(uname -m)"
  set_install_prefix
  local common_flags
  configure_common_flags
  common_flags+=("-DGGML_CCACHE=OFF" "-DCMAKE_INSTALL_PREFIX=$install_prefix")
  available dnf && dnf_install
  if [ -n "$containerfile" ]; then 
      clone_and_build_ramalama
  fi
  clone_and_build_whisper_cpp
  common_flags+=("-DLLAMA_CURL=ON")
  case "$containerfile" in
    ramalama)
      if [ "$uname_m" = "x86_64" ] || [ "$uname_m" = "aarch64" ]; then
        common_flags+=("-DGGML_KOMPUTE=ON" "-DKOMPUTE_OPT_DISABLE_VULKAN_VERSION_CHECK=ON")
      else
        common_flags+=("-DGGML_BLAS=ON" "-DGGML_BLAS_VENDOR=OpenBLAS")
      fi
      ;;
  esac

  clone_and_build_llama_cpp
  rm -rf /var/cache/*dnf* /opt/rocm-*/lib/*/library/*gfx9*
  ldconfig # needed for libraries
}

main "$@"
