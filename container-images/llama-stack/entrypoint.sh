#! /bin/bash

# shellcheck source=/dev/null
source /.venv/bin/activate

if [ $# -eq 0 ]; then
    exec bash
else
    case "$RAMALAMA_RUNTIME" in
        vllm)
            export VLLM_URL="$RAMALAMA_URL"
            unset RAMALAMA_URL
            ;;
        llama.cpp)
            export LLAMA_CPP_SERVER_URL="$RAMALAMA_URL"
            unset RAMALAMA_URL
            ;;
        mlx|*)
            ;;
    esac

    exec "$@"
fi
