#!/usr/bin/env bash

# ramalama.sh demo script.
# This script will demonstrate a lot of the features of RamaLama, concentrating
# on the security features.

#set -eou pipefail
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
    if ! command -v ramalama > /dev/null; then
	echo "$0 requires the ramalama package be installed"
	exit 1
    fi
    clear
}


version() {
    # RamaLama version
    exec_color "ramalama version"

    # RamaLama info
    exec_color "ramalama info | less"

    read -r -p "--> clear"
    clear
}

pull() {
    clear

    echo_color "Remove smollm:135m model if previously pulled"
    exec_color "ramalama rm --ignore smollm:135m"
    echo ""

    echo_color "RamaLama Pulling Ollama Image smollm:135m"
    exec_color "ramalama pull smollm:135m"
    echo ""

    echo_color "RamaLama List all AI Models in local store"
    exec_color "ramalama ls | grep --color smollm:135m"
    echo ""

    echo_color "Show RamaLama container images"
    exec_color "podman images | grep ramalama"
    echo ""

    read -r -p "--> clear"
    clear
}

run() {
    echo_color "Serve granite via RamaLama run"
    exec_color "ramalama --dryrun run granite | grep --color podman"
    echo ""
    exec_color "ramalama --dryrun run granite | grep --color \"quay.io[^ ]*\""
    echo ""
    exec_color "ramalama --dryrun run granite | grep --color -- --cap-drop.*privileges"
    echo ""
    exec_color "ramalama --dryrun run granite | grep --color -- --network.*none"
    echo ""

    echo_color "run granite via RamaLama run"
    exec_color "ramalama run --ngl 0 granite"
    echo ""

    read -r -p "--> clear"
    clear
}

serve() {
    echo_color "Serve granite via RamaLama model service"
    exec_color "ramalama serve --port 8080 --name granite-service -d granite"
    echo ""

    echo_color "List RamaLama containers"
    exec_color "ramalama ps"
    echo ""

    echo_color "list containers via Podman"
    exec_color "podman ps "
    echo ""

    echo_color "Use web browser to show interaction"
    exec_color "firefox http://localhost:8080"

    echo_color "Stop the ramalama container"
    exec_color "ramalama stop granite-service"
    echo ""

    echo_color "Serve granite via RamaLama model service"
    exec_color "ramalama serve --port 8085 --api llama-stack --name granite-service -d granite"
    echo ""

    echo_color "Use web browser to show interaction"
    exec_color "firefox http://localhost:8085"

    echo_color "Use web browser to show interaction"
    exec_color "firefox http://localhost:8085/v1/openai"

    echo_color "Stop the ramalama container"
    exec_color "ramalama stop granite-service"
    echo ""

    echo_color "List RamaLama containers"
    exec_color "ramalama ps"
    echo ""

    read -r -p "--> clear"
    clear
}

kubernetes() {
    echo_color "Convert smollm:135m model from Ollama into a OCI content"
    exec_color "ramalama convert smollm:135m quay.io/ramalama/smollm:1.0"
    echo ""

    echo_color "List created image"
    exec_color "podman images | grep --color quay.io/ramalama/smollm"
    echo ""

    echo_color "Generate kubernetes YAML file for sharing OCI AI Model"
    exec_color "ramalama serve --generate kube --name smollm-service oci://quay.io/ramalama/smollm:1.0"
    echo ""

    echo_color "Examine kubernetes YAML file "
    exec_color "less smollm-service.yaml"
    echo ""

    read -r -p "--> clear"
    clear
}

quadlet() {
    echo_color "Generate Quadlet files for sharing AI Model"
    exec_color "ramalama serve --generate quadlet --name smollm-service oci://quay.io/ramalama/smollm:1.0"
    echo ""

    echo_color "Examine quadlet volume file "
    exec_color "less smollm-service.volume"
    echo ""

    echo_color "Examine quadlet image file "
    exec_color "less smollm-service.image"
    echo ""

    echo_color "Examine quadlet container file "
    exec_color "less smollm-service.container"
    echo ""

    read -r -p "--> clear"
    clear
}

multi-modal() {
    echo_color "Serve smolvlm via RamaLama model service"
    exec_color "ramalama serve --port 8080  --pull=never  --name multi-modal -d smolvlm"
    echo ""

    echo_color "Use web browser to show interaction"
    exec_color "firefox \"$(dirname \"$1\")/camera-demo.html\""

    echo_color "Stop the ramalama container"
    exec_color "ramalama stop multi-modal	"
    echo ""

    read -r -p "--> clear"
    clear
}

setup

version

pull

run

serve

kubernetes

quadlet

multi-modal

echo_color "End of Demo"
echo "Thank you!"
