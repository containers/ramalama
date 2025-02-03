#!/usr/bin/env bash

# Bash does not easily pass arrays as a single arg to a function.  So, make this a global var in the script.
CMAKE_FLAGS=""

function cmakeCheckWarnings() {
  awk -v rc=0 '/CMake Warning:/ { rc=1 } 1; END {exit rc}'
}

function cloneAndBuild() {
  local git_repo=${1}
  local git_sha=${2}
  local install_prefix=${3}
  local work_dir=$(mktemp -d)

  git clone ${git_repo} ${work_dir}
  cd ${work_dir}
  git submodule update --init --recursive
  git reset --hard ${git_sha}
  echo "-------------CMAKE FLAGS---------------------"
  echo "${CMAKE_FLAGS[@]}"
  cmake -B build ${CMAKE_FLAGS[@]} 2>&1 | cmakeCheckWarnings
  cmake --build build --config Release -j$(nproc) -v 2>&1 | cmakeCheckWarnings
  cmake --install build --prefix ${install_prefix} 2>&1 | cmakeCheckWarnings
  cd -
  rm -rf ${work_dir}
}

function dnfPrepUbi() {

  local url="https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm"
  local uname_m=$(uname -m)

  dnf install -y ${url}
  crb enable # this is in epel-release, can only install epel-release via url
  dnf copr enable -y slp/mesa-krunkit epel-9-${uname_m}
  url="https://mirror.stream.centos.org/9-stream/AppStream/${uname_m}/os/"
  dnf config-manager --add-repo ${url}
  url="http://mirror.centos.org/centos/RPM-GPG-KEY-CentOS-Official"
  curl --retry 8 --retry-all-errors -o /etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-Official ${url}
  rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-Official
}

function main() {
  set -ex

  local container_image=${1}
  local install_prefix=/usr
  local package_list
  local whisper_cpp_sha=${WHISPER_CPP_SHA:-8a9ad7844d6e2a10cddf4b92de4089d7ac2b14a9}
  local llama_cpp_sha=${LLAMA_CPP_SHA:-aa6fb1321333fae8853d0cdc26bcb5d438e650a1}
  local common_rpms=("python3" "python3-pip" "python3-argcomplete" "python3-dnf-plugin-versionlock" "gcc-c++" "cmake" "vim" "procps-ng" "git" "dnf-plugins-core" "libcurl-devel")
  local vulkan_rpms=("vulkan-headers" "vulkan-loader-devel" "vulkan-tools" "spirv-tools" "glslc" "glslang")
  local intel_rpms=("intel-oneapi-mkl-sycl-devel" "intel-oneapi-dnnl-devel" "intel-oneapi-compiler-dpcpp-cpp" "intel-level-zero" "oneapi-level-zero" "oneapi-level-zero-devel" "intel-compute-runtime")

  CMAKE_FLAGS=("-DGGML_CCACHE=OFF" "-DGGML_NATIVE=OFF" "-DBUILD_SHARED_LIBS=NO")

  case ${container_image} in
    ramalama)
      dnfPrepUbi
      dnf --enablerepo=ubi-9-appstream-rpms install -y mesa-vulkan-drivers "${common_rpms[@]}" "${vulkan_rpms[@]}"
      CMAKE_FLAGS+=("-DGGML_KOMPUTE=ON" "-DKOMPUTE_OPT_DISABLE_VULKAN_VERSION_CHECK=ON")
    ;;
    rocm)
      dnfPrepUbi
      dnf --enablerepo=ubi-9-appstream-rpms install -y "${common_rpms[@]}" "${vulkan_rpms[@]}" rocm-dev hipblas-devel rocblas-devel
      CMAKE_FLAGS+=("-DGGML_HIP=ON" "-DAMDGPU_TARGETS=${AMDGPU_TARGETS:-gfx1010,gfx1030,gfx1032,gfx1100,gfx1101,gfx1102}")
    ;;
    cuda)
      dnf install -y "${common_rpms[@]}" gcc-toolset-12
      . /opt/rh/gcc-toolset-12/enable
      CMAKE_FLAGS+=("-DGGML_CUDA=ON" "-DCMAKE_EXE_LINKER_FLAGS=-Wl,--allow-shlib-undefined")
      install_prefix=/llama-cpp
    ;;
    vulkan)
      dnfPrepUbi
      dnf --enablerepo=ubi-9-appstream-rpms install -y mesa-vulkan-drivers "${common_rpms[@]}" "${vulkan_rpms[@]}"
      CMAKE_FLAGS+=("-DGGML_VULKAN=1")
    ;;
    asahi)
      dnf copr enable -y @asahi/fedora-remix-branding
      dnf install -y asahi-repos
      dnf install -y mesa-vulkan-drivers "${vulkan_rpms[@]}" "${common_rpms[@]}"
      CMAKE_FLAGS+=("-DGGML_VULKAN=1")
    ;;
    intel-gpu)
      dnf install -y ${common_rpms[@]} ${intel_rpms[@]}
      CMAKE_FLAGS+=("-DGGML_SYCL=ON" "-DCMAKE_C_COMPILER=icx" "-DCMAKE_CXX_COMPILER=icpx")
      install_prefix=/llama-cpp
      source /opt/intel/oneapi/setvars.sh
    ;;
  esac

  cloneAndBuild https://github.com/ggerganov/whisper.cpp ${whisper_cpp_sha} ${install_prefix}
  CMAKE_FLAGS+=("-DLLAMA_CURL=ON")
  cloneAndBuild https://github.com/ggerganov/llama.cpp ${llama_cpp_sha} ${install_prefix}
  dnf -y clean all
  rm -rf /var/cache/*dnf* /opt/rocm-*/lib/*/library/*gfx9*
  ldconfig # needed for libraries

}

main "$@"
