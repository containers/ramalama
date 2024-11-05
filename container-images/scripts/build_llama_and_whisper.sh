#!/bin/bash

main() {
  set -e

  local llama_cpp_sha="$1"
  local whisper_cpp_sha="$2"
  local install_prefix="$3"
  local build_flag_1="$4"
  local build_flag_2="$5"
  git clone https://github.com/ggerganov/llama.cpp
  cd llama.cpp
  git reset --hard "$llama_cpp_sha"
  cmake -B build -DGGML_CCACHE=0 "$build_flag_1" "$build_flag_2" \
    -DCMAKE_INSTALL_PREFIX="$install_prefix"
  cmake --build build --config Release -j"$(nproc)"
  cmake --install build
  cd ..
  rm -rf llama.cpp

  git clone https://github.com/ggerganov/whisper.cpp
  cd whisper.cpp
  git reset --hard "$whisper_cpp_sha"
  cmake -B build -DGGML_CCACHE=0 "$build_flag_1" "$build_flag_2" \
    -DBUILD_SHARED_LIBS=NO -DCMAKE_INSTALL_PREFIX="$install_prefix"
  cmake --build build --config Release -j"$(nproc)"
  cmake --install build
  mv build/bin/main "$install_prefix/bin/whisper-main"
  mv build/bin/server "$install_prefix/bin/whisper-server"
  cd ..
  rm -rf whisper.cpp
}

main "$@"

