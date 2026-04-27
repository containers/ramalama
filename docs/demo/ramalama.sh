#!/usr/bin/env bash

# ramalama.sh demo script.
# This script will demonstrate a lot of the features of RamaLama, concentrating
# on the security features.

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
if [[ -z "${SCRIPT_DIR}" ]]; then
   echo "Error: Could not determine script directory." >&2
   exit 1
fi
REPO_ROOT="$( cd -- "${SCRIPT_DIR}/../.." &> /dev/null && pwd )"

#set -eou pipefail
IFS=$'\n\t'

# Setting up some colors for helping read the demo output.
# Comment out any of the below to turn off that color.
bold=$(tput bold)
cyan=$(tput setaf 6)
reset=$(tput sgr0)

# Allow overriding browser (default: firefox)
BROWSER="${BROWSER:-firefox}"

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
    exec_color "$BROWSER http://localhost:8080"
    echo ""

    echo_color "Stop the ramalama container"
    exec_color "ramalama stop granite-service"
    echo ""

    echo_color "Serve granite via RamaLama model service"
    exec_color "ramalama serve --port 8085 --api llama-stack --name granite-service -d granite"
    echo ""

    echo_color "Waiting for the model service to come up"
    exec_color "timeout 25 bash -c 'until curl -s -f -o /dev/null http://localhost:8085/v1/openai/v1/models; do sleep 2; done'"
    echo ""

    echo_color "Inference against the model using llama-stack API"
    exec_color "printf \"\\n\"; curl --no-progress-meter http://localhost:8085/v1/openai/v1/chat/completions -H \"Content-Type: application/json\" -d '{ \"model\": \"library/granite3.1-dense\", \"messages\": [{\"role\": \"user\", \"content\": \"Tell me a joke\"}], \"stream\": false }' | grep -Po '\"content\"\\s*:\\s*\"\\K[^\"]*' | head -1"
    echo ""

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
    exec_color "ramalama serve --port 8080 --name multi-modal -d smolvlm"
    echo ""

    echo_color "Use web browser to show interaction"
    exec_color "$BROWSER \"${SCRIPT_DIR}/camera-demo.html\""
    echo ""

    echo_color "Stop the ramalama container"
    exec_color "ramalama stop multi-modal"
    echo ""

    read -r -p "--> clear"
    clear
}

ensure_demo_tools() {
    DEMO_TOOLS_DIR="${REPO_ROOT}/../ramalama-demo-tools"
    if [ ! -d "$DEMO_TOOLS_DIR" ]; then
        if ! git clone https://github.com/bmahabirbu/ramalama-demo-tools "$DEMO_TOOLS_DIR"; then
            echo "Error: failed to clone ramalama-demo-tools into $DEMO_TOOLS_DIR" >&2
            return 1
        fi
    else
        if ! git -C "$DEMO_TOOLS_DIR" pull --ff-only; then
            echo "Error: failed to update $DEMO_TOOLS_DIR" >&2
            return 1
        fi
    fi
}

mcp () {
    echo_color "Start MCP server and use it with a LLM"

    # Check if gemini.env exists
    if [ -f "${REPO_ROOT}/../gemini.env" ]; then
        # shellcheck disable=SC1091
        source "${REPO_ROOT}/../gemini.env"
        GEMINI_AVAILABLE=true
    else
        echo_color "Warning: gemini.env not found. Skipping Gemini chat."
        GEMINI_AVAILABLE=false
    fi

    ensure_demo_tools

    # Start MCP server directly (not via exec_color) so we can capture PID
    cd "$DEMO_TOOLS_DIR" || return
    MCP_LOG="${DEMO_TOOLS_DIR}/mcp-server.log"
    echo -n "
${bold}$ nohup uv run mcp-test-server.py >$MCP_LOG 2>&1 &${reset}"
    read -r
    nohup uv run mcp-test-server.py >"$MCP_LOG" 2>&1 &
    MCP_PID=$!
    trap 'kill "$MCP_PID" 2>/dev/null' EXIT

    # Wait for MCP server to be ready
    echo_color "Waiting for MCP server to start..."
    timeout 15 bash -c 'until curl -s -f -o /dev/null http://127.0.0.1:8000/mcp 2>/dev/null; do sleep 1; done'

    # Run ramalama server
    cd "$REPO_ROOT" || return
    exec_color "ramalama run phi4 --mcp http://127.0.0.1:8000/mcp"
    # show /tool list of tools and click 1 to show output
    # prompt "list all the files on my desktop"
    # prompt "what is Dan Walsh's favorite food?"

    # Run ramalama chat only if gemini.env was loaded
    if [ "$GEMINI_AVAILABLE" = true ]; then
        exec_color "ramalama chat --url https://generativelanguage.googleapis.com/v1beta/openai --model gemini-2.5-flash --mcp http://127.0.0.1:8000/mcp"
    fi

    # Kill MCP server if still running
    if ps -p $MCP_PID > /dev/null 2>&1; then
        kill $MCP_PID
    fi

    read -r -p "--> clear"
    clear
}


rag (){
    cd "$REPO_ROOT" || return
    echo_color "Create a rag database and use it with a LLM"
    exec_color "echo Brian loves cheese > test.md"
    exec_color "ramalama rag test.md test:latest"
    exec_color "ramalama run phi4 --rag test:latest"
    # prompt "what food does brian like?"
    ensure_demo_tools
    exec_color "podman load -i ${DEMO_TOOLS_DIR}/podbook.tar"
    # # We need this timer so the port is cleared out from the previous run
    # # This is a workaround a fix is needed in the future
    time sleep 5
    exec_color "ramalama run phi4 --rag podbook:latest"
    # prompt "Who is the author of Podman in Action?"
    # prompt "Who did the author dedicate the book to?"
    read -r -p "--> clear"
    clear
}

DEMO_MODE="${1:-}"
ALLOWED_FUNCTIONS=(version pull run serve kubernetes quadlet rag)

if [[ "$DEMO_MODE" == "mcp" || "$DEMO_MODE" == "multi-modal" || "$DEMO_MODE" == "all" ]]; then
    shift
elif [[ $# -gt 0 ]]; then
    cmd="$1"
    if printf '%s\n' "${ALLOWED_FUNCTIONS[@]}" | grep -Fxq -- "$cmd"; then
        setup
        "$cmd" "${@:2}"
        echo_color "End of Demo"
        echo "Thank you!"
        exit 0
    else
        echo "Error: unknown command '$cmd'"
        echo "Usage: $0 [all|multi-modal|mcp|${ALLOWED_FUNCTIONS[*]}]"
        exit 1
    fi
fi

# Default to all demos if no mode specified
DEMO_MODE="${DEMO_MODE:-all}"

setup

version

pull

run

serve

kubernetes

quadlet

if [[ "$DEMO_MODE" == "all" ]]; then
    multi-modal
    mcp
    rag
elif [[ "$DEMO_MODE" == "mcp" ]]; then
    mcp
    rag
else
    multi-modal
fi

echo_color "End of Demo"
echo "Thank you!"
