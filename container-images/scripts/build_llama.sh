#!/bin/bash

DEFAULT_LLAMA_CPP_COMMIT="15fa3c493bfcd040b5f4dcb29e1c998a0846de16" # b8920
MESA_VULKAN_VERSION=25.3.6-102.fc43

dnf_install_remoting() {
    dnf install -y libdrm-devel

    if [ "${RAMALAMA_IMAGE_BUILD_REMOTING_BACKEND:-}" ]; then
        dnf install -y meson libepoxy-devel python3-yaml
    fi
}

dnf_install_intel_gpu() {
  local intel_rpms=("intel-oneapi-mkl-sycl-devel" "intel-oneapi-dnnl-devel"
    "intel-oneapi-mkl-devel" "intel-oneapi-mkl-sycl-distributed-dft-devel"
    "intel-oneapi-compiler-dpcpp-cpp" "intel-level-zero"
    "oneapi-level-zero" "oneapi-level-zero-devel" "intel-compute-runtime")
  dnf install -y "${intel_rpms[@]}"
}

dnf_install_asahi() {
  dnf copr enable -y @asahi/fedora-remix-branding
  dnf install -y asahi-repos
  dnf install -y mesa-vulkan-drivers "${vulkan_rpms[@]}"
}

dnf_install_cuda() {
  local gcc_toolset_version=14
  dnf install -y gcc-toolset-${gcc_toolset_version}
  # shellcheck disable=SC1090
  . /opt/rh/gcc-toolset-${gcc_toolset_version}/enable
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
    pigz
}

dnf_install_rocm() {
  if [ "${ID}" = "fedora" ]; then
    dnf update -y
    dnf install -y --releasever 44 rocm-core-devel hipblas-devel rocblas-devel rocm-hip-devel rocwmma-devel
  else
    add_stream_repo "AppStream"
    dnf install -y rocm-dev hipblas-devel rocblas-devel rocwmma-dev
  fi

  rm_non_ubi_repos
}

dnf_install_s390_ppc64le() {
  dnf install -y "openblas-devel"
}

dnf_install_openvino() {
  dnf install -y ocl-icd-devel opencl-headers
}

dnf_install_mesa() {
  if [ "${ID}" = "fedora" ]; then
    dnf copr enable -y slp/mesa-libkrun-vulkan
    dnf install -y mesa-vulkan-drivers-$MESA_VULKAN_VERSION virglrenderer \
      "${vulkan_rpms[@]}"
    dnf versionlock add mesa-vulkan-drivers-$MESA_VULKAN_VERSION
  elif [ "${ID}" = "openEuler" ]; then
    dnf install -y mesa-vulkan-drivers virglrenderer "${vulkan_rpms[@]}"
  else # virglrenderer not available on RHEL or EPEL
    dnf install -y mesa-vulkan-drivers "${vulkan_rpms[@]}"
  fi

  rm_non_ubi_repos
}

dnf_install() {
  local rpm_exclude_list="selinux-policy,container-selinux"
  local rpm_list=("python3-dnf-plugin-versionlock"
    "gcc-c++" "cmake" "vim" "procps-ng" "git-core"
    "dnf-plugins-core" "gawk" "openssl-devel")
  local vulkan_rpms=("vulkan-headers" "vulkan-loader-devel" "vulkan-tools"
    "spirv-tools" "spirv-headers-devel" "glslc" "glslang")
  if is_rhel_based; then
    dnf_install_epel # All the UBI-based ones
    dnf --enablerepo=ubi-9-appstream-rpms install -y "${rpm_list[@]}" --exclude "${rpm_exclude_list}"
  else
    dnf install -y "${rpm_list[@]}" --exclude "${rpm_exclude_list}"
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
  elif [ "$containerfile" = "openvino" ]; then
    dnf_install_openvino
  elif [ "$containerfile" = "remoting" ]; then
    dnf_install_remoting

    if [ "${RAMALAMA_IMAGE_BUILD_REMOTING_BACKEND:-}" == "vulkan" ]; then
        # install Vulkan for running it as a (Linux) backend remoting library
        dnf install -y mesa-vulkan-drivers "${vulkan_rpms[@]}"
    fi
  fi

  dnf -y clean all
}

dnf_install_runtime_deps() {
  local runtime_pkgs=()
  if [ "$containerfile" = "ramalama" ]; then
    # install python3 in the ramalama container to support a non-standard use-case
    runtime_pkgs+=(python3 python3-pip)
    if [ "$uname_m" = "x86_64" ] || [ "$uname_m" = "aarch64" ]; then
      dnf copr enable -y slp/mesa-libkrun-vulkan
      runtime_pkgs+=(vulkan-loader vulkan-tools "mesa-vulkan-drivers-$MESA_VULKAN_VERSION")
    else
      runtime_pkgs+=(openblas)
    fi
  elif [[ "$containerfile" = rocm* ]]; then
    runtime_pkgs+=(hipblas rocblas rocm-hip rocm-runtime rocsolver)
  elif [ "$containerfile" = "asahi" ]; then
    dnf copr enable -y @asahi/fedora-remix-branding
    dnf install -y asahi-repos
    runtime_pkgs+=(vulkan-loader vulkan-tools mesa-vulkan-drivers)
  elif [ "$containerfile" = "cuda" ]; then
    # install python3.12 in the cuda container to support a non-standard use-case
    runtime_pkgs+=(python3.12 python3.12-pip)
    ln -sf python3.12 /usr/bin/python3
  elif [ "$containerfile" = "intel-gpu" ]; then
    runtime_pkgs+=(
      clinfo lspci procps-ng
      intel-compute-runtime intel-level-zero
      intel-oneapi-runtime-compilers intel-oneapi-runtime-dnnl intel-oneapi-runtime-mkl
      intel-oneapi-mkl-core intel-oneapi-mkl-sycl-blas intel-oneapi-mkl-sycl-dft
      oneapi-level-zero
    )
  elif [ "$containerfile" = "openvino" ]; then
    runtime_pkgs+=(ocl-icd intel-opencl intel-npu-driver)
  elif [ "$containerfile" = "remoting" ]; then
    runtime_pkgs+=(libdrm)
    if [ "${RAMALAMA_IMAGE_BUILD_REMOTING_BACKEND:-}" == "vulkan" ]; then
        # install Vulkan for running it as a (Linux) backend remoting library
        dnf copr enable -y slp/mesa-libkrun-vulkan
        runtime_pkgs+=(vulkan-loader vulkan-tools "mesa-vulkan-drivers-$MESA_VULKAN_VERSION")
    fi
  fi

  if [[ "${RAMALAMA_IMAGE_BUILD_DEBUG_MODE:-}" == y ]]; then
      runtime_pkgs+=(gdb strace)
  fi

  if [ ${#runtime_pkgs[@]} -gt 0 ]; then
    local enablerepo_flag=""
    [ "$containerfile" = "openvino" ] && enablerepo_flag="--enablerepo=updates-testing"
    dnf install -y $enablerepo_flag --setopt=install_weak_deps=false "${runtime_pkgs[@]}"
  fi
  dnf -y clean all
}

cmake_check_warnings() {
  awk -v rc=0 '/CMake Warning:/ { rc=1 } 1; END {exit rc}'
}

setup_build_env() {
  # external scripts may reference unbound variables
  set +ux
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
  elif [ "$containerfile" = "intel-gpu" ]; then
    # shellcheck disable=SC1091
    source /opt/intel/oneapi/setvars.sh
  elif [ "$containerfile" = "openvino" ]; then
    # shellcheck disable=SC1091
    source /opt/intel/openvino/setupvars.sh
  fi
  set -ux
}

cmake_steps() {
  (
    # This makes llama.cpp build a generic binary, similar to an rpm build
    SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct)
    export SOURCE_DATE_EPOCH
    local cmake_flags=("$@")
    cmake -B build "${cmake_flags[@]}" 2>&1 | cmake_check_warnings
    local build_config=Release
    if [[ "${RAMALAMA_IMAGE_BUILD_DEBUG_MODE:-}" == y ]]; then
        build_config=Debug
    fi
    cmake --build build --config "$build_config" -j"$(nproc)" 2>&1 | cmake_check_warnings
    cmake --install build 2>&1 | cmake_check_warnings
  )
}

configure_common_flags() {
  common_flags=(
      "-DGGML_CCACHE=OFF" "-DGGML_RPC=ON" "-DCMAKE_INSTALL_PREFIX=/tmp/install"
      "-DLLAMA_BUILD_TESTS=OFF" "-DLLAMA_BUILD_EXAMPLES=OFF" "-DGGML_BUILD_TESTS=OFF" "-DGGML_BUILD_EXAMPLES=OFF"
  )
  if [ "$containerfile" = "cann" ]; then
      :
  elif [ "$containerfile" = "openvino" ]; then
      # openvino backend doesn't support GGML_BACKEND_DL — upstream is missing
      # GGML_BACKEND_DL_IMPL(ggml_backend_openvino_reg) in ggml-openvino.cpp.
      # Until that's added, we also can't use GGML_CPU_ALL_VARIANTS.
      common_flags+=("-DGGML_NATIVE=OFF")
  else
      common_flags+=("-DGGML_NATIVE=OFF" "-DGGML_BACKEND_DL=ON" "-DGGML_CPU_ALL_VARIANTS=ON")
  fi
  if [[ "${RAMALAMA_IMAGE_BUILD_DEBUG_MODE:-}" == y ]]; then
      common_flags+=("-DGGML_CMAKE_BUILD_TYPE=Debug")
  else
      common_flags+=("-DGGML_CMAKE_BUILD_TYPE=Release")
  fi

  case "$containerfile" in
  ramalama)
    if [ "$uname_m" = "x86_64" ] || [ "$uname_m" = "aarch64" ]; then
      common_flags+=("-DGGML_VULKAN=ON")
    elif [ "$uname_m" = "s390x" ] || [ "$uname_m" = "ppc64le" ]; then
      common_flags+=("-DGGML_BLAS=ON" "-DGGML_BLAS_VENDOR=OpenBLAS")
    fi
    if [ "$uname_m" = "s390x" ]; then
      common_flags+=("-DARCH_FLAGS=-march=z15")
    fi
    ;;
  rocm*)
    if [ "${ID}" = "fedora" ]; then
      common_flags+=("-DCMAKE_HIP_COMPILER_ROCM_ROOT=/usr")
    fi

    common_flags+=("-DGGML_HIP=ON" "-DGGML_HIP_ROCWMMA_FATTN=ON" "-DGPU_TARGETS=${GPU_TARGETS:-gfx803;gfx900;gfx906;gfx908;gfx90a;gfx942;gfx1010;gfx1030;gfx1032;gfx1100;gfx1101;gfx1102;gfx1200;gfx1201;gfx1151}")
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
  cann)
    common_flags+=("-DGGML_CANN=ON" "-DSOC_TYPE=Ascend910B3")
    ;;
  musa)
    common_flags+=("-DGGML_MUSA=ON" "-DCMAKE_EXE_LINKER_FLAGS=-Wl,--allow-shlib-undefined")
    ;;
  openvino)
    common_flags+=("-DGGML_OPENVINO=ON")
    ;;
  remoting)
      common_flags+=("-DGGML_VIRTGPU=ON")

      if [[ "${RAMALAMA_IMAGE_BUILD_REMOTING_BACKEND:-}" ]]; then
          common_flags+=("-DGGML_VIRTGPU_BACKEND=ON")

          if [[ "${RAMALAMA_IMAGE_BUILD_REMOTING_BACKEND:-}" == "vulkan" ]]; then
              common_flags+=("-DGGML_VULKAN=ON")
          else
              echo "ERROR: unknown API Remoting backend requested: ${RAMALAMA_IMAGE_BUILD_REMOTING_BACKEND:-}" >&2
              echo "ERROR: expected 'vulkan' or unset. Got '${RAMALAMA_IMAGE_BUILD_REMOTING_BACKEND:-}'." >&2
              exit 1
          fi
      fi
    ;;
  esac
}

clone_and_build_llama_cpp() {
  local llama_cpp_commit="${LLAMA_CPP_PULL_REF:-$DEFAULT_LLAMA_CPP_COMMIT}"
  git_clone_specific_commit "${LLAMA_CPP_REPO:-https://github.com/ggml-org/llama.cpp}" "$llama_cpp_commit"
  cmake_steps "${common_flags[@]}"
  cd ..
  if [[ "${RAMALAMA_IMAGE_BUILD_DEBUG_MODE:-}" != y ]]; then
      rm -rf llama.cpp
  fi
}

cleanup() {
  available dnf && dnf -y clean all
  ldconfig # needed for libraries
}

clone_and_build_virglrenderer() {
    virgl_commit=${VIRGL_COMMIT:-main-linux}
    virgl_repo=${VIRGL_REPO:-https://gitlab.freedesktop.org/kpouget/virglrenderer}
    git_clone_specific_commit "$virgl_repo" "$virgl_commit"

    local buildtype=release
    if [[ "${RAMALAMA_IMAGE_BUILD_DEBUG_MODE:-}" == y ]]; then
        buildtype=debug
    fi

    meson setup ./build -Dvenus=true -Dapir=true --buildtype="$buildtype" --prefix=/tmp/install/
    ninja -C ./build
    ninja -C ./build install

    cd ..

    if [[ "${RAMALAMA_IMAGE_BUILD_DEBUG_MODE:-}" != y ]]; then
        rm -rf virglrenderer
    fi
}

main() {
  # shellcheck disable=SC1091
  source /etc/os-release

  set -eux -o pipefail

  # shellcheck disable=SC1091
  source "$(dirname "$0")/lib.sh"

  local containerfile=${1-""}
  local uname_m
  uname_m="$(uname -m)"

  if [ "${2-""}" == "runtime" ]; then
      dnf_install_runtime_deps
      exit
  fi

  local common_flags
  configure_common_flags

  available dnf && dnf_install

  setup_build_env

  clone_and_build_llama_cpp

  if [ "$containerfile" = "remoting" ] && [ "${RAMALAMA_IMAGE_BUILD_REMOTING_BACKEND:-}" ]; then
      clone_and_build_virglrenderer
  fi

  cleanup
}

main "$@"
