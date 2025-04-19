#!/bin/bash

available() {
  command -v "$1" >/dev/null
}

dnf_install_intel_gpu() {
  local intel_rpms=("intel-oneapi-mkl-sycl-devel" "intel-oneapi-dnnl-devel" \
                  "intel-oneapi-compiler-dpcpp-cpp" "intel-level-zero" \
                  "oneapi-level-zero" "oneapi-level-zero-devel" "intel-compute-runtime")
  dnf install -y "${intel_rpms[@]}"

  # shellcheck disable=SC1091
  . /opt/intel/oneapi/setvars.sh
}

dnf_remove() {
  dnf remove -y \
      python3-devel \
      libcurl-devel \
      gcc \
      gcc-c++ \
      make \
      cmake \
      findutils
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
  dnf install -y git \
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
  if [ "$containerfile" = "rocm" ]; then
    if [ "${ID}" = "fedora" ]; then
      dnf install -y rocm-core-devel hipblas-devel rocblas-devel rocm-hip-devel
    else
      add_stream_repo "AppStream"
      dnf install -y rocm-dev hipblas-devel rocblas-devel
    fi
  fi

  rm_non_ubi_repos
}

dnf_install_s390() {
  # I think this was for s390, maybe ppc also
  dnf install -y "openblas-devel"
}

add_stream_repo() {
  local url="https://mirror.stream.centos.org/9-stream/$1/$uname_m/os/"
  dnf config-manager --add-repo "$url"
  url="http://mirror.centos.org/centos/RPM-GPG-KEY-CentOS-Official"
  local file="/etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-Official"
  if [ ! -e $file ]; then
    curl --retry 8 --retry-all-errors -o $file "$url"
    rpm --import $file
  fi
}

rm_non_ubi_repos() {
  local dir="/etc/yum.repos.d"
  rm -rf $dir/mirror.stream.centos.org_9-stream_* $dir/epel* $dir/_copr:*
}

is_rhel_based() { # doesn't include openEuler
  [[ "${ID}" == "rhel" || "${ID}" == "redhat" || "${ID}" == "centos" ]]
}

dnf_install_mesa() {
  if is_rhel_based; then
    dnf copr enable -y slp/mesa-krunkit "epel-9-$uname_m"
    add_stream_repo "AppStream"
  fi

  dnf install -y mesa-vulkan-drivers "${vulkan_rpms[@]}"
  rm_non_ubi_repos
}

dnf_install_epel() {
  local url="https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm"
  dnf reinstall -y "$url" || dnf install -y "$url"
  crb enable # this is in epel-release, can only install epel-release via url
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

  if [[ "${ID}" == "openEuler" ]]; then
    dnf install -y ffmpeg
  else
    dnf install -y ffmpeg-free
  fi
  rm_non_ubi_repos
}

dnf_install() {
  local rpm_list=("python3" "python3-pip" \
                  "python3-argcomplete" "python3-dnf-plugin-versionlock" \
                  "python3-devel" "gcc-c++" "cmake" "vim" "procps-ng" "git" \
                  "dnf-plugins-core" "libcurl-devel" "gawk")
  local vulkan_rpms=("vulkan-headers" "vulkan-loader-devel" "vulkan-tools" \
                     "spirv-tools" "glslc" "glslang")
  if is_rhel_based; then
    dnf_install_epel # All the UBI-based ones
    dnf --enablerepo=ubi-9-appstream-rpms install -y "${rpm_list[@]}"
  else
    dnf install -y "${rpm_list[@]}"
  fi

  if [ "$containerfile" = "ramalama" ]; then
    if [ "$uname_m" = "x86_64" ] || [ "$uname_m" = "aarch64" ]; then
      dnf_install_mesa # on x86_64 and aarch64 we use vulkan via mesa 
    else
      dnf_install_s390
    fi
  elif [[ "$containerfile" =~ rocm* ]]; then
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
    cann_in_sys_path=/usr/local/Ascend/ascend-toolkit;
    cann_in_user_path=$HOME/Ascend/ascend-toolkit;
    if [ -f "${cann_in_sys_path}/set_env.sh" ]; then
        # shellcheck disable=SC1091
        source ${cann_in_sys_path}/set_env.sh;
        export LD_LIBRARY_PATH=${cann_in_sys_path}/latest/lib64:${cann_in_sys_path}/latest/${uname_m}-linux/devlib:${LD_LIBRARY_PATH};
        export LIBRARY_PATH=${cann_in_sys_path}/latest/lib64:${LIBRARY_PATH};
    elif [ -f "${cann_in_user_path}/set_env.sh" ]; then
        # shellcheck disable=SC1091
        source "$HOME/Ascend/ascend-toolkit/set_env.sh";
        export LD_LIBRARY_PATH=${cann_in_user_path}/latest/lib64:${cann_in_user_path}/latest/${uname_m}-linux/devlib:${LD_LIBRARY_PATH};
        export LIBRARY_PATH=${cann_in_user_path}/latest/lib64:${LIBRARY_PATH};
    else
        echo "No Ascend Toolkit found";
        exit 1;
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
  if [ "$containerfile" = "cuda" ] || [ "$containerfile" = "intel-gpu" ] || [ "$containerfile" = "cann" ]; then
    echo "/tmp/install"
  else
    echo "/usr"
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
  local llama_cpp_sha="daa422881a0ec7944771bcc8ff8de34d11f5bd3b"
  local install_prefix
  install_prefix=$(set_install_prefix)
  git clone https://github.com/ggml-org/llama.cpp
  cd llama.cpp
  git submodule update --init --recursive
  git reset --hard "$llama_cpp_sha"
  cmake_steps "${common_flags[@]}"
  install -m 755 build/bin/rpc-server "$install_prefix"/bin/rpc-server
  cd ..
  rm -rf llama.cpp
}

clone_and_build_ramalama() {
  git clone https://github.com/containers/ramalama
  cd ramalama
  git submodule update --init --recursive
  python3 -m pip install . --prefix="$1"
  cd ..
  rm -rf ramalama
}

main() {
  # shellcheck disable=SC1091
  source /etc/os-release

  set -ex -o pipefail

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
    clone_and_build_ramalama "${install_prefix}"
  fi

  setup_build_env
  clone_and_build_whisper_cpp
  common_flags+=("-DLLAMA_CURL=ON" "-DGGML_RPC=ON")
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
  available dnf && dnf_remove
  rm -rf /var/cache/*dnf* /opt/rocm-*/lib/*/library/*gfx9*
  ldconfig # needed for libraries
}

main "$@"
