#!/usr/bin/bash -ex

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
export ARMREPO=${ARMREPO:-"quay.io/rhatdan"}
export REPO=${REPO:-"quay.io/ramalama"}

release() {
    version=$(bin/ramalama -q version)
    minor_version=${version%.*}
    DEST=${REPO}/"$1"
    podman manifest rm "$1" 2>/dev/null|| true
    podman manifest create "$1"
    id=$(podman image inspect "${DEST}" --format '{{ .Id }}')
    podman manifest add "$1" "$id"
    id=$(podman pull -q --arch arm64 "${ARMREPO}"/"$1")
    podman manifest add "$1" "$id"
    podman manifest inspect "$1"
    digest=$(podman image inspect "${DEST}" --format '{{ .Digest }}' | cut -f2 -d':')
    podman manifest push --all "$1" "${DEST}:${digest}"
    podman manifest push --all "$1" "${DEST}:${version}"
    podman manifest push --all "$1" "${DEST}:${minor_version}"
    podman manifest push --all "$1" "${DEST}"
    podman manifest rm "$1"
}

case ${1} in
    ramalama-cli)
	podman run --pull=never --rm "${REPO}/$1" version
	release "$1"
	;;
    openvino)
	podman run --pull=never --rm "${REPO}/$1" ls -l bin/ovms
	release "$1"
	;;
    llama-stack)
	podman run --pull=never --rm "${REPO}/$1" llama -h
	release "$1"
	;;
    stable-diffusion)
	podman run --pull=never --rm "${REPO}/$1" sd -h
	release "$1"
	;;
    *)
	podman run --pull=never --rm "${REPO}/$1" ls -l /usr/bin/llama-server
	podman run --pull=never --rm "${REPO}/$1" ls -l /usr/bin/llama-run
	podman run --pull=never --rm "${REPO}/$1" ls -l /usr/bin/whisper-server
	podman run --pull=never --rm "${REPO}/$1"-rag rag_framework load

	release "$1"
	release "$1"-whisper-server
	release "$1"-llama-server
	release "$1"-rag
	;;
esac
