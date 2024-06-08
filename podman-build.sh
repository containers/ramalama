#!/bin/bash

build() {
  cd $1
  image_name=$(echo $1 | sed "s#/#:#g" | sed "s#container-images:##g")
  podman build -t $image_name .
  cd -
}

main() {
  set -ex -o pipefail

  build "container-images/podman-llm/latest"

  for i in container-images/*/*; do
    build "$i"
  done
}

main

