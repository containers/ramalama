#!/bin/bash

clone_and_build_triton() {
  local triton_sha="e5be006"
  "pip${PYTHON_VERSION}" install ninja cmake wheel pybind11
  git clone https://github.com/OpenAI/triton.git
  cd triton
  git checkout $triton_sha
  cd python
  "pip${PYTHON_VERSION}" install .
  cd ../..
}

patch_cuda() {
  # Origin: https://stackoverflow.com/questions/25635318/how-to-get-heredoc-to-not-escape-my-characters
  pushd /usr/local/cuda/include/crt
  patch <<EOF
--- a/math_functions.h  00:02:30.815134398 +0300
+++ b/math_functions.h  00:03:30.815134398 +0300
@@ -2547,7 +2547,7 @@
  *
  * \\note_accuracy_double
  */
-extern __DEVICE_FUNCTIONS_DECL__ __device_builtin__ double                 sinpi(double x);
+extern __DEVICE_FUNCTIONS_DECL__ __device_builtin__ double                 sinpi(double x) noexcept (true);
 /**
  * \\ingroup CUDA_MATH_SINGLE
  * \\brief Calculate the sine of the input argument
@@ -2570,7 +2570,7 @@
  *
  * \\note_accuracy_single
  */
-extern __DEVICE_FUNCTIONS_DECL__ __device_builtin__ float                  sinpif(float x);
+extern __DEVICE_FUNCTIONS_DECL__ __device_builtin__ float                  sinpif(float x) noexcept (true);
 /**
  * \\ingroup CUDA_MATH_DOUBLE
  * \\brief Calculate the cosine of the input argument
@@ -2592,7 +2592,7 @@
  *
  * \\note_accuracy_double
  */
-extern __DEVICE_FUNCTIONS_DECL__ __device_builtin__ double                 cospi(double x);
+extern __DEVICE_FUNCTIONS_DECL__ __device_builtin__ double                 cospi(double x) noexcept (true);
 /**
  * \\ingroup CUDA_MATH_SINGLE
  * \\brief Calculate the cosine of the input argument
@@ -2614,7 +2614,7 @@
  *
  * \\note_accuracy_single
  */
-extern __DEVICE_FUNCTIONS_DECL__ __device_builtin__ float                  cospif(float x);
+extern __DEVICE_FUNCTIONS_DECL__ __device_builtin__ float                  cospif(float x) noexcept (true);
 /**
  * \\ingroup CUDA_MATH_DOUBLE
  * \\brief  Calculate the sine and cosine of the first input argument
EOF
  popd
}

# looks like clang++ call led to the usage
# patch from https://github.com/gentoo/gentoo/pull/42594/commits/84622e59e1510e7457a4aefb0c7919572b043bd1
patch_hip(){
  pushd /
  patch -p1 <<EOF
--- /usr/include/hip/hip_version.h	2025-05-02 00:00:00.000000000 +0000
+++ /usr/include/hip/hip_version.h.orig	2025-06-18 12:43:33.283147644 +0000
@@ -12,6 +12,14 @@
 #define HIP_VERSION    (HIP_VERSION_MAJOR * 10000000 + HIP_VERSION_MINOR * 100000 + HIP_VERSION_PATCH)
 
 #define __HIP_HAS_GET_PCH 1
+// Workaround for https://gcc.gnu.org/bugzilla/show_bug.cgi?id=115740
+#if defined(__has_include) && defined(__cplusplus) && defined(__HIP__)
+  #if __has_include("bits/c++config.h")
+    #include <bits/c++config.h>
+    #undef __glibcxx_assert
+    #define __glibcxx_assert(cond)
+  #endif
+#endif
 
 #endif
EOF
  popd
}

gcc_15_fixup() {
  if gcc --version | grep ' 15'; then
     if [[ "$VLLM_TARGET_DEVICE" == cuda ]]; then
        # max 14 supported with nvcc
        ln -s  /usr/bin/cpp-14  /usr/local/bin/cpp
        ln -s  /usr/bin/g++-14  /usr/local/bin/g++
        ln -s  /usr/bin/g++-14  /usr/local/bin/c++
        ln -s  /usr/bin/gcc-14  /usr/local/bin/gcc
        patch_cuda
     fi
     if [[ "$VLLM_TARGET_DEVICE" == rocm ]]; then
        patch_hip
     fi
  fi
}

clone_and_build_vllm() {
  local vllm_sha="aed8468642740c9a8486d6dde334d9a4e80a687f"
  "python${PYTHON_VERSION}" -m ensurepip
  if [[ "$VLLM_TARGET_DEVICE" = rocm ]]; then
     clone_and_build_triton
  fi
  git clone https://github.com/vllm-project/vllm
  cd vllm
  git reset --hard "$vllm_sha"
  gcc_15_fixup
  if [[ "$VLLM_TARGET_DEVICE" == cuda ]]; then
     # workaround, test dep at build time ?
     "pip${PYTHON_VERSION}" install nvidia-cusparselt-cu12==0.6.3
     # libcusparseLt.so.0
     export LD_LIBRARY_PATH=/usr/local/lib/python${PYTHON_VERSION}/site-packages/cusparselt/lib
     set_nvcc_threads
  fi
  if [[ "$VLLM_TARGET_DEVICE" = rocm ]]; then
    "pip${PYTHON_VERSION}" install --upgrade numba \
       scipy \
       "huggingface-hub[cli,hf_transfer]" \
       setuptools_scm
    "pip${PYTHON_VERSION}" install "numpy<2"
    # pip version did not worked
    cp -r /usr/lib/python3.13/site-packages/amdsmi "/usr/local/lib/python${PYTHON_VERSION}/site-packages/amdsmi"
    # This issue only seen in this env (not on the fedora host)
    # /usr/lib64/rocm/llvm/bin/clang++ --offload-arch=gfx1100 -o test.hip.o  -c test2.hip -v
    ln -s /usr/lib64/rocm/llvm/lib/clang/18/amdgcn /usr/lib64/rocm/llvm/lib/clang/18/lib/amdgcn
  fi
  "pip${PYTHON_VERSION}" install -r "requirements/$VLLM_TARGET_DEVICE.txt"

  # marlin generation
  if [[ "$VLLM_TARGET_DEVICE" = cuda ]]; then
      cp -r  "/usr/local/lib64/python${PYTHON_VERSION}/site-packages/markupsafe" "/usr/lib64/python${PYTHON_VERSION}"
      cp -r  "/usr/local/lib/python${PYTHON_VERSION}/site-packages/jinja2" "/usr/lib64/python${PYTHON_VERSION}"
  fi

  # had issue with -e
  "pip${PYTHON_VERSION}" install .
  cd ..
}

set_nvcc_threads() {
  if [[ ! -v NVCC_THREADS ]] ; then
    # to avoid OOM, cicc can grow to 19G
    local max_by_mem=$(( $(free -m | awk 'NR==2{print $7}') / 19456 ))
    local max_by_cpu
    max_by_cpu=$(nproc)
    if [[ $max_by_mem -le $max_by_cpu ]]; then
      NVCC_THREADS=$max_by_mem
    else
      NVCC_THREADS=$max_by_cpu
    fi
    if [[ $NVCC_THREADS -lt 1 ]]; then
       NVCC_THREADS=1
    fi
    export NVCC_THREADS
 fi
 echo "NVCC_THREADS=${NVCC_THREADS}"
}

get_python_ver_y(){
   python3 --version 2>&1 | grep -oP 'Python \d+\.\K\d+'
}

set_python_version(){
   local y_ver
   y_ver=$(get_python_ver_y)
   if [[ $y_ver -ge 12 ]];then
      PYTHON_VERSION=3.12
   else
      PYTHON_VERSION=3.$y_ver
   fi
}

add_stream_repo() {
  local url="https://mirror.stream.centos.org/9-stream/$1/$UNAME_M/os/"
  dnf config-manager --add-repo "$url"
  url="http://mirror.centos.org/centos/RPM-GPG-KEY-CentOS-Official"
  local file="/etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-Official"
  if [ ! -e $file ]; then
    curl --retry 8 --retry-all-errors -o $file "$url"
    rpm --import $file
  fi
}

is_rhel_based() { # doesn't include openEuler
  [[ "${ID}" == "rhel" || "${ID}" == "redhat" || "${ID}" == "centos" ]]
}

dnf_install_epel() {
  local rpm_exclude_list="selinux-policy,container-selinux"
  local url="https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm"
  dnf reinstall -y "$url" || dnf install -y "$url" --exclude "${rpm_exclude_list}"
  crb enable # this is in epel-release, can only install epel-release via url
}

rm_centos_repos() {
  local dir="/etc/yum.repos.d"
  rm -rf $dir/mirror.stream.centos.org_9-stream_*
}

dnf_install_repos() {
  if is_rhel_based && [[ $ID != fedora ]]; then
    dnf_install_epel
    add_stream_repo "AppStream"
    add_stream_repo "BaseOS"
    add_stream_repo "CRB"
  fi
  yum install -y numactl-devel
  rm_centos_repos
}

main() {
  # shellcheck disable=SC1091
  source /etc/os-release

  set -ex -o pipefail
  export VLLM_TARGET_DEVICE=${1-"cpu"}
  UNAME_M=$(uname -m)
  if [[ ${UNAME_M} == aarch64 ]]; then
     export VLLM_CPU_DISABLE_AVX512=true
  fi
  dnf_install_repos
  set_python_version

  RPM_PKGS=(git gcc-c++ "python${PYTHON_VERSION}-devel" cargo openssl-devel numactl-devel patch)
  if [ "${ID}" = "fedora" ]; then
      RPM_PKGS+=(sentencepiece-devel)
  fi

  case "$VLLM_TARGET_DEVICE" in
  cpu)
    export PIP_EXTRA_INDEX_URL="https://download.pytorch.org/whl/cpu"
    ;;
  cuda)
     export PIP_EXTRA_INDEX_URL="https://download.pytorch.org/whl/cu128"
     nv_arch=sbsa
     if [[ $UNAME_M = x86_64 ]]; then
	     nv_arch=x86_64
     fi
     RPM_PKGS+=(procps-ng cudnn9)
     if [[ $ID == fedora ]]; then
         curl -o /etc/yum.repos.d/cuda-fedora41.repo \
           --max-time 10 \
           --retry 5 \
           --retry-delay 0 \
           --retry-max-time 40 \
           https://developer.download.nvidia.com/compute/cuda/repos/fedora41/$nv_arch/cuda-fedora41.repo
	 # in case of ubi use cuda from image
	 RPM_PKGS+=(gcc14-c++ cuda-12-8 libcusparse-devel-12-8 libcusparse-12-8 libnccl-devel)
     fi
     # aarch64 fedora nvidia repo incomplete
     # for cudadnn (Deprecated use ?) required ATM an x86_64 as well
      curl -o /etc/yum.repos.d/cuda-rhel_9.repo \
       --max-time 10 \
       --retry 5 \
       --retry-delay 0 \
       --retry-max-time 40 \
       https://developer.download.nvidia.com/compute/cuda/repos/rhel9/$nv_arch/cuda-rhel9.repo
     export CUDACXX=/usr/local/cuda-12.8/bin/nvcc
    ;;
  rocm)
     export PIP_EXTRA_INDEX_URL="https://download.pytorch.org/whl/rocm6.2.4"
     RPM_PKGS+=(rocm-core-devel hipblas-devel rocblas-devel rocm-hip-devel miopen-devel rccl-devel
                rocrand-devel hiprand-devel hipfft-devel hipsparse-devel hipcub-devel rocthrust-devel
		hipsolver-devel hipblaslt-devel rocminfo clang amdsmi)
     export ROCM_PATH=/usr
     # CMAKE_MODULE_PATH FindHIP
     ln -s /usr/lib64/cmake/ /usr/lib
     # similar to /usr/local/lib64/python3.12/site-packages/torch/share/cmake/Caffe2/public/LoadHIP.cmake
     ln -s /usr/include /usr/include/rocm-core
     ln -s /usr/ /usr/llvm
     export CMAKE_MODULE_PATH=/usr/lib64/cmake/hip
     export PYTORCH_ROCM_ARCH="gfx90a;gfx942;gfx1100;gfx1101;gfx1200;gfx1201"
    ;;
  *)
      echo only cpu, rocm, cuda supported \""$VLLM_TARGET_DEVICE"\" given
      exit 42
    ;;
  esac
  dnf install -y "${RPM_PKGS[@]}"
  clone_and_build_vllm
}

main "$@"
