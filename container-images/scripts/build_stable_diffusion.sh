#!/bin/bash

python_version() {
  if python3 -c 'import sys; exit(not (sys.version_info.major == 3 and sys.version_info.minor == 11))'; then
    echo "python3.11"
  else
    echo "python3"
  fi
}

available() {
  command -v "$1" >/dev/null
}

dnf_remove() {
  dnf -y clean all
}

dnf_install_epel() {
  local rpm_exclude_list="selinux-policy,container-selinux"
  local url="https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm"
  dnf reinstall -y "$url" || dnf install -y "$url" --exclude "${rpm_exclude_list}"
  crb enable # this is in epel-release, can only install epel-release via url
}

is_rhel_based() { # doesn't include openEuler
  [[ "${ID}" == "rhel" || "${ID}" == "redhat" || "${ID}" == "centos" ]]
}

dnf_install() {
  local rpm_exclude_list="selinux-policy,container-selinux"
  local rpm_list=("${PYTHON}" "${PYTHON}-pip"
    "${PYTHON}-devel" "gcc-c++" "cmake" "vim" "procps-ng" "git-core"
    "dnf-plugins-core" "libcurl-devel" "gawk")
  
  if is_rhel_based; then
    dnf_install_epel
    dnf --enablerepo=ubi-9-appstream-rpms install -y "${rpm_list[@]}" --exclude "${rpm_exclude_list}"
  else
    dnf install -y "${rpm_list[@]}" --exclude "${rpm_exclude_list}"
  fi
  
  if [[ "${PYTHON}" == "python3.11" ]]; then
    ln -sf /usr/bin/python3.11 /usr/bin/python3
  fi
  
  dnf -y clean all
}

cmake_check_warnings() {
  # There has warning "CMake Warning:Manually-specified variables were not used by the project" during compile of custom ascend kernels of ggml cann backend.
  # Should remove "cann" judge condition when this warning are fixed in llama.cpp/whisper.cpp
  if [ "$containerfile" != "cann" ]; then
    awk -v rc=0 '/CMake Warning:/ { rc=1 } 1; END {exit rc}'
  else
    awk '/CMake Warning:/ {print $0}'
  fi
}

setup_build_env() {
  if [ "$containerfile" = "cann" ]; then
    # source build env
    cann_in_sys_path=/usr/local/Ascend/ascend-toolkit
    cann_in_user_path=$HOME/Ascend/ascend-toolkit
    if [ -f "${cann_in_sys_path}/set_env.sh" ]; then
      # shellcheck disable=SC1091
      source ${cann_in_sys_path}/set_env.sh
      export LD_LIBRARY_PATH="${cann_in_sys_path}/latest/lib64:${cann_in_sys_path}/latest/${uname_m}-linux/devlib:${LD_LIBRARY_PATH}"
      export LIBRARY_PATH="${cann_in_sys_path}/latest/lib64:${LIBRARY_PATH}"
    elif [ -f "${cann_in_user_path}/set_env.sh" ]; then
      # shellcheck disable=SC1091
      source "$HOME/Ascend/ascend-toolkit/set_env.sh"
      export LD_LIBRARY_PATH="${cann_in_user_path}/latest/lib64:${cann_in_user_path}/latest/${uname_m}-linux/devlib:${LD_LIBRARY_PATH}"
      export LIBRARY_PATH="${cann_in_user_path}/latest/lib64:${LIBRARY_PATH}"
    else
      echo "No Ascend Toolkit found"
      exit 1
    fi
  fi
}

cmake_steps() {
  local cmake_flags=("$@")
  cmake -B build "${cmake_flags[@]}" 2>&1 | cmake_check_warnings
  cmake --build build --config Release -j"$(nproc)" 2>&1 | cmake_check_warnings
  cmake --install build 2>&1 | cmake_check_warnings
}

set_install_prefix() {
  if [ "$containerfile" = "cuda" ] || [ "$containerfile" = "intel-gpu" ] || [ "$containerfile" = "cann" ] || [ "$containerfile" = "musa" ]; then
    echo "/tmp/install"
  else
    echo "/usr"
  fi
}

configure_common_flags() {
  common_flags=("-DGGML_NATIVE=OFF" "-DGGML_CMAKE_BUILD_TYPE=Release")
  case "$containerfile" in
  rocm*)
    if [ "${ID}" = "fedora" ]; then
      common_flags+=("-DCMAKE_HIP_COMPILER_ROCM_ROOT=/usr")
    fi
    common_flags+=("-DGGML_HIP=ON" "-DAMDGPU_TARGETS=${AMDGPU_TARGETS:-gfx1010,gfx1012,gfx1030,gfx1032,gfx1100,gfx1101,gfx1102,gfx1103,gfx1151,gfx1200,gfx1201}")
    ;;
  cuda)
    common_flags+=("-DGGML_CUDA=ON" "-DCMAKE_EXE_LINKER_FLAGS=-Wl,--allow-shlib-undefined" "-DCMAKE_CUDA_FLAGS=\"-U__ARM_NEON -U__ARM_NEON__\"")
    ;;
  vulkan | asahi)
    common_flags+=("-DGGML_VULKAN=1")
    ;;
  intel-gpu)
    common_flags+=("-DGGML_SYCL=ON" "-DCMAKE_C_COMPILER=icx" "-DCMAKE_CXX_COMPILER=icpx")
    ;;
  cann)
    common_flags+=("-DGGML_CANN=ON" "-DSOC_TYPE=Ascend910B3")
    ;;
  musa)
    common_flags+=("-DGGML_MUSA=ON")
    ;;
  esac
}

clone_and_build_stable_diffusion_cpp() {
  # Using the correct leejet/stable-diffusion.cpp repository
  local install_prefix
  install_prefix=$(set_install_prefix)
  common_flags+=("-DGGML_STABLE_DIFFUSION=ON")
  
  # Clone the correct repository
  git clone https://github.com/leejet/stable-diffusion.cpp
  cd stable-diffusion.cpp
  git submodule update --init --recursive
  # Use master branch (latest stable)
  cmake_steps "${common_flags[@]}"
  
  # Install the stable diffusion binary
  install -m 755 build/bin/sd "$install_prefix"/bin/sd
  cd ..
  rm -rf stable-diffusion.cpp
}

install_ramalama() {
  if [ -e "pyproject.toml" ]; then
    $PYTHON -m pip install . --prefix="$1"
  fi
}

main() {
  # shellcheck disable=SC1091
  source /etc/os-release

  set -ex -o pipefail
  export PYTHON
  PYTHON=$(python_version)

  local containerfile=${1-""}
  local install_prefix
  install_prefix=$(set_install_prefix)
  local uname_m
  uname_m="$(uname -m)"
  local common_flags
  configure_common_flags
  common_flags+=("-DGGML_CCACHE=OFF" "-DCMAKE_INSTALL_PREFIX=${install_prefix}")
  
  available dnf && dnf_install
  if [ -n "$containerfile" ]; then
    install_ramalama "${install_prefix}"
  fi

  setup_build_env
  # Build stable diffusion only (no whisper)
  clone_and_build_stable_diffusion_cpp
  
  available dnf && dnf_remove
  rm -rf /var/cache/*dnf*
  ldconfig # needed for libraries
}

main "$@" 