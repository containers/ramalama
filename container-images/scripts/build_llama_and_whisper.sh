#!/bin/bash

python_version() {
  local pyversion
  pyversion=$(python3 --version)
  # $2 is empty when no Python is installed, so just install python3
  if [ -n "$pyversion" ]; then
    local pystr="$pyversion
Python 3.10"
    if [ "$pystr" == "$(sort --version-sort <<<"$pystr")" ]; then
      echo "python3.11"
      return
    fi
  fi
  echo "python3"
}

dnf_install_intel_gpu() {
  local intel_rpms=("intel-oneapi-mkl-sycl-devel" "intel-oneapi-dnnl-devel"
    "intel-oneapi-compiler-dpcpp-cpp" "intel-level-zero"
    "oneapi-level-zero" "oneapi-level-zero-devel" "intel-compute-runtime")
  dnf install -y "${intel_rpms[@]}"

  # shellcheck disable=SC1091
  . /opt/intel/oneapi/setvars.sh
}

dnf_remove() {
  dnf -y clean all
}

dnf_install_asahi() {
  dnf copr enable -y @asahi/fedora-remix-branding
  dnf install -y asahi-repos
  dnf install -y mesa-vulkan-drivers "${vulkan_rpms[@]}"
}

dnf_install_cuda() {
  dnf install -y gcc-toolset-12
  # shellcheck disable=SC1091
  . /opt/rh/gcc-toolset-12/enable
}

dnf_install_cann() {
  # just for openeuler build environment, does not need to push to ollama github
  dnf install -y git-core \
    gcc \
    gcc-c++ \
    make \
    cmake \
    findutils \
    yum \
    curl-devel \
    pigz
}

dnf_install_rocm() {
  if [ "${ID}" = "fedora" ]; then
    dnf update -y
    dnf install -y rocm-core-devel hipblas-devel rocblas-devel rocm-hip-devel
  else
    add_stream_repo "AppStream"
    dnf install -y rocm-dev hipblas-devel rocblas-devel
  fi

  rm_non_ubi_repos
}

dnf_install_s390_ppc64le() {
  dnf install -y "openblas-devel"
}

dnf_install_mesa() {
  if [ "${ID}" = "fedora" ]; then
    dnf copr enable -y slp/mesa-libkrun-vulkan
    dnf install -y mesa-vulkan-drivers-25.0.7-101.fc42 virglrenderer \
      "${vulkan_rpms[@]}"
    dnf versionlock add mesa-vulkan-drivers-25.0.7-101.fc42
  elif [ "${ID}" = "openEuler" ]; then
    dnf install -y mesa-vulkan-drivers virglrenderer "${vulkan_rpms[@]}"
  else # virglrenderer not available on RHEL or EPEL
    dnf install -y mesa-vulkan-drivers "${vulkan_rpms[@]}"
  fi

  rm_non_ubi_repos
}

# There is no ffmpeg-free package in the openEuler repository. openEuler can use ffmpeg,
# which also has the same GPL/LGPL license as ffmpeg-free.
dnf_install_ffmpeg() {
  if is_rhel_based; then
    dnf_install_epel
    add_stream_repo "AppStream"
    add_stream_repo "BaseOS"
    add_stream_repo "CRB"
  fi

  if [ "${ID}" = "openEuler" ]; then
    dnf install -y ffmpeg
  else
    dnf install -y ffmpeg-free
  fi

  rm_non_ubi_repos
}

dnf_install() {
  local rpm_exclude_list="selinux-policy,container-selinux"
  local rpm_list=("${PYTHON}" "${PYTHON}-pip"
    "python3-argcomplete" "python3-dnf-plugin-versionlock"
    "${PYTHON}-devel" "gcc-c++" "cmake" "vim" "procps-ng" "git-core"
    "dnf-plugins-core" "libcurl-devel" "gawk")
  local vulkan_rpms=("vulkan-headers" "vulkan-loader-devel" "vulkan-tools"
    "spirv-tools" "glslc" "glslang")
  if is_rhel_based; then
    dnf_install_epel # All the UBI-based ones
    dnf --enablerepo=ubi-9-appstream-rpms install -y "${rpm_list[@]}" --exclude "${rpm_exclude_list}"
  else
    dnf install -y "${rpm_list[@]}" --exclude "${rpm_exclude_list}"
  fi
  if [[ "${PYTHON}" == "python3.11" ]]; then
    ln -sf /usr/bin/python3.11 /usr/bin/python3
  fi
  if [ "$containerfile" = "ramalama" ]; then
    if [ "$uname_m" = "x86_64" ] || [ "$uname_m" = "aarch64" ]; then
      dnf_install_mesa # on x86_64 and aarch64 we use vulkan via mesa
    else
      dnf_install_s390_ppc64le
    fi
  elif [[ "$containerfile" = rocm* ]]; then
    dnf_install_rocm
  elif [ "$containerfile" = "asahi" ]; then
    dnf_install_asahi
  elif [ "$containerfile" = "cuda" ]; then
    dnf_install_cuda
  elif [ "$containerfile" = "intel-gpu" ]; then
    dnf_install_intel_gpu
  elif [ "$containerfile" = "cann" ]; then
    dnf_install_cann
  fi

  dnf_install_ffmpeg

  if [[ "${RAMALAMA_IMAGE_BUILD_DEBUG_MODE:-}" == y ]]; then
      dnf install -y gdb strace
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
  local build_config=Release
  if [[ "${RAMALAMA_IMAGE_BUILD_DEBUG_MODE:-}" == y ]]; then
      build_config=Debug
  fi
  cmake --build build --config "$build_config" -j"$(nproc)" 2>&1 | cmake_check_warnings
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
  common_flags=("-DGGML_NATIVE=OFF")
  if [[ "${RAMALAMA_IMAGE_BUILD_DEBUG_MODE:-}" == y ]]; then
      common_flags+=("-DGGML_CMAKE_BUILD_TYPE=Debug")
  else
      common_flags+=("-DGGML_CMAKE_BUILD_TYPE=Release")
  fi

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

clone_and_build_whisper_cpp() {
  local DEFAULT_WHISPER_COMMIT="7745fcf32846006128f16de429cfe1677c963b30"
  local whisper_cpp_commit="${WHISPER_CPP_PULL_REF:-$DEFAULT_WHISPER_COMMIT}"
  local whisper_flags=("${common_flags[@]}")
  whisper_flags+=("-DBUILD_SHARED_LIBS=OFF")
  # See: https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md#compilation-options
  if [ "$containerfile" = "musa" ]; then
    whisper_flags+=("-DCMAKE_POSITION_INDEPENDENT_CODE=ON")
  fi

  git_clone_specific_commit "${WHISPER_CPP_REPO:-https://github.com/ggerganov/whisper.cpp}" "$whisper_cpp_commit"
  cmake_steps "${whisper_flags[@]}"
  mkdir -p "$install_prefix/bin"
  cd ..
  if [[ "${RAMALAMA_IMAGE_BUILD_DEBUG_MODE:-}" != y ]]; then
      rm -rf whisper.cpp
  fi
}

clone_and_build_llama_cpp() {
  local DEFAULT_LLAMA_CPP_COMMIT=9961d244f2df6baf40af2f1ddc0927f8d91578c8
  local llama_cpp_commit="${LLAMA_CPP_PULL_REF:-$DEFAULT_LLAMA_CPP_COMMIT}"
  local install_prefix
  install_prefix=$(set_install_prefix)
  git_clone_specific_commit "${LLAMA_CPP_REPO:-https://github.com/ggml-org/llama.cpp}" "$llama_cpp_commit"
  cmake_steps "${common_flags[@]}"
  install -m 755 build/bin/rpc-server "$install_prefix"/bin/rpc-server
  cd ..
  if [[ "${RAMALAMA_IMAGE_BUILD_DEBUG_MODE:-}" != y ]]; then
      rm -rf llama.cpp
  fi
}

install_ramalama() {
  if [ -e "pyproject.toml" ]; then
    $PYTHON -m pip install . --prefix="$1"
  fi
}

install_entrypoints() {
  if [ -e "container-images" ]; then
    install -d "$install_prefix"/bin
    install -m 755 \
      container-images/scripts/llama-server.sh \
      container-images/scripts/whisper-server.sh \
      container-images/scripts/build_rag.sh \
      container-images/scripts/doc2rag \
      container-images/scripts/rag_framework \
      "$install_prefix"/bin
  fi
}

cleanup() {
  available dnf && dnf_remove
  rm -rf /var/cache/*dnf* /opt/rocm-*/lib/*/library/*gfx9*
  ldconfig # needed for libraries
}

add_common_flags() {
  common_flags+=("-DLLAMA_CURL=ON" "-DGGML_RPC=ON")
  case "$containerfile" in
  ramalama)
    if [ "$uname_m" = "x86_64" ] || [ "$uname_m" = "aarch64" ]; then
      common_flags+=("-DGGML_VULKAN=ON")
    elif [ "$uname_m" = "s390x" ] || [ "$uname_m" = "ppc64le" ]; then
      common_flags+=("-DGGML_BLAS=ON" "-DGGML_BLAS_VENDOR=OpenBLAS")
    fi
    ;;
  esac
}

main() {
  # shellcheck disable=SC1091
  source /etc/os-release

  set -ex -o pipefail
  export PYTHON
  PYTHON=$(python_version)

  # shellcheck disable=SC1091
  source container-images/scripts/lib.sh

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

  install_entrypoints
  setup_build_env
  if [ "$uname_m" != "s390x" ]; then
    clone_and_build_whisper_cpp
  fi

  add_common_flags
  clone_and_build_llama_cpp
  cleanup
}

main "$@"
