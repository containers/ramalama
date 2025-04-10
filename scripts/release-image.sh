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
export ARMREPO=${ARMREPO:"quay.io/rhatdan"}
export REPO=${REPO:"quay.io/ramalama"}

release-arm() {
    podman push "${REPO}/$1" "${ARMREPO}/$1"

    release-ramalama "$1"
    case ${1} in
	ramalama-cli|     llama-stack)
	;;
	*)
	    podman push "${REPO}"/"$1"-whisper-server "${ARMREPO}"/"$1"-whisper-server
	    podman push "${REPO}"/"$1"-llama-server "${ARMREPO}"/"$1"-llama-server
	    ;;
    esac
}

release-ramalama() {
    podman push "${REPO}"/"$1" "${REPO}"/"$1":0.7.3
    podman push "${REPO}"/"$1" "${REPO}"/"$1":0.7
    podman push "${REPO}"/"$1"
}

release() {
    release-ramalama "$1"
    case ${1} in
	ramalama-cli|     llama-stack)
	;;
	*)
	    release-ramalama "$1"-whisper-server
	    release-ramalama "$1"-llama-server
	    release-ramalama "$1"-rag
	    ;;
    esac
}

case ${1} in
    ramalama-cli)
	podman run --rm "${REPO}"/"$1" /usr/bin/ramalama version
	;;
    llama-stack)
	podman run --rm "${REPO}"/"$1" /usr/bin/llama
	;;
    *)
	podman run --rm "${REPO}"/"$1" ls -l /usr/bin/llama-server
	podman run --rm "${REPO}"/"$1" ls -l /usr/bin/llama-run
	podman run --rm "${REPO}"/"$1" ls -l /usr/bin/whisper-server
	podman run --rm "${REPO}"/"$1"-rag rag_framework load
	;;
esac

uname_m=$(uname -m)
if [ "${uname_m}" == "x86_64" ]; then
    release "$1"
else
    release-arm "$1"
fi
