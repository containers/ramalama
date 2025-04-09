#!/bin/bash -ex

if [ -z "$1" ]; then
    echo "Usage: $0 IMAGE" >&2
    exit 1
fi

# Prior to running this script, I run
#    make build IMAGE=$IMAGE
#         Where image is one of: ramalama, asahi, cann and cuda on both X86 and ARM platforms.
#    Then on ARM Platform I first run release-image.sh $IMAGE to push the image
#    to the ARMREPO
# Once that is complete I run this script for each one of the $IMAGEs
# This script assumes that ARM images have been pushed to ARMREPO from
# MACS

release-rhatdan() {
    podman push quay.io/ramalama/"$1" quay.io/rhatdan/"$1"
    podman push quay.io/ramalama/"$1"-whisper-server quay.io/rhatdan/"$1"-whisper-server
    podman push quay.io/ramalama/"$1"-llama-server quay.io/rhatdan/"$1"-llama-server
}

release-ramalama() {
    podman push quay.io/ramalama/"$1" quay.io/ramalama/"$1":0.7.3
    podman push quay.io/ramalama/"$1" quay.io/ramalama/"$1":0.7
    podman push quay.io/ramalama/"$1"
}
release() {
    release-ramalama "$1"
    release-ramalama "$1"-whisper-server
    release-ramalama "$1"-llama-server
    release-ramalama "$1"-rag
}

podman run quay.io/ramalama/"$1" ls -l /usr/bin/llama-server
podman run quay.io/ramalama/"$1" ls -l /usr/bin/llama-run
podman run quay.io/ramalama/"$1" ls -l /usr/bin/whisper-server
podman run quay.io/ramalama/"$1"-rag rag_framework load

uname_m=$(uname -m)
if [ "${uname_m}" == "x86_64" ]; then
    release "$1"
else
    release-rhatdan "$1"
fi
