#!/usr/bin/env bash

# ramalama.sh demo script.
# This script will demonstrate a lot of the features of RamaLama, concentrating
# on the security features.

set -eou pipefail
IFS=$'\n\t'

# Setting up some colors for helping read the demo output.
# Comment out any of the below to turn off that color.
bold=$(tput bold)
cyan=$(tput setaf 6)
reset=$(tput sgr0)

echo_color() {
    echo "${cyan}$1${reset}"
}

exec_color() {
    echo -n "
${bold}$ $1${reset}"
    read -r
    bash -c "$1"
}

setup() {
    command -v ramalama > /dev/null
    if [[ $? != 0 ]]; then
	echo $0 requires the ramalama package be installed
	exit 1
    fi
    clear
}


version() {
    # RamaLama version
    exec_color "ramalama version"

    # RamaLama info
    exec_color "ramalama info | less"

    read -p "--> clear"
    clear
}

pull() {
    clear

    echo_color "Remove tiny model if previously pulled"
    exec_color "ramalama rm --ignore tiny"
    echo ""

    echo_color "RamaLama Pulling Ollama Image tiny"
    exec_color "ramalama pull tiny"
    echo ""

    echo_color "RamaLama List all AI Models in local store"
    exec_color "ramalama ls | grep --color tiny"
    echo ""

    echo_color "Show RamaLama container images"
    exec_color "podman images | grep ramalama"
    echo ""

    read -p "--> clear"
    clear
}

run() {
    echo_color "Serve granite via RamaLama run"
    exec_color "ramalama --dryrun run granite | grep --color podman"
    echo ""
    exec_color "ramalama --dryrun run granite | grep --color quay.io.*latest"
    echo ""
    exec_color "ramalama --dryrun run granite | grep --color -- --cap-drop.*privileges"
    echo ""
    exec_color "ramalama --dryrun run granite | grep --color -- --network.*none"
    echo ""

    echo_color "run granite via RamaLama rune"
    exec_color "ramalama run --ngl 0 granite"
    echo ""

    read -p "--> clear"
    clear
}

serve() {
    echo_color "Serve granite via RamaLama model service"
    exec_color "ramalama serve --name granite-service -d granite"
    echo ""

    echo_color "List RamaLama containers"
    exec_color "ramalama ps"
    echo ""

    echo_color "list containers via Podman"
    exec_color "podman ps "
    echo ""

    echo_color "Stop the ramalama container"
    exec_color "ramalama stop granite-service"
    echo ""

    echo_color "List RamaLama containers"
    exec_color "ramalama ps"
    echo ""

    read -p "--> clear"
    clear
}

kubernetes() {
    echo_color "Convert tiny model from Ollama into a OCI content"
    exec_color "ramalama convert tiny quay.io/ramalama/tiny:1.0"
    echo ""

    echo_color "List created image"
    exec_color "podman images | grep --color quay.io/ramalama/tiny"
    echo ""

    echo_color "Generate kubernetes YAML file for sharing OCI AI Model"
    exec_color "ramalama serve --generate kube --name tiny-service oci://quay.io/ramalama/tiny:1.0"
    echo ""

    echo_color "Examine kubernetes YAML file "
    exec_color "less tiny-service.yaml"
    echo ""

    read -p "--> clear"
    clear
}

quadlet() {
    echo_color "Generate Quadlet files for sharing AI Model"
    exec_color "ramalama serve --generate quadlet --name tiny-service oci://quay.io/ramalama/tiny:1.0"
    echo ""

    echo_color "Examine quadlet volume file "
    exec_color "less tiny-service.volume"
    echo ""

    echo_color "Examine quadlet image file "
    exec_color "less tiny-service.image"
    echo ""

    echo_color "Examine quadlet container file "
    exec_color "less tiny-service.container"
    echo ""

    read -p "--> clear"
    clear
}

setup

version

pull

run

kubernetes

quadlet

echo_color "End of Demo"
echo "Thank you!"
