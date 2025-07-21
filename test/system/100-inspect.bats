#!/usr/bin/env bats

load helpers
load helpers.registry
load setup_suite

# bats test_tags=distro-integration
@test "ramalama inspect GGUF model" {
    MODEL=c_$(safename)
    run_ramalama 22 inspect ${MODEL}
    is "$output" "Error: ${MODEL} does not exists" "error on missing models"
    
    run_ramalama pull tiny
    run_ramalama inspect tiny

    is "${lines[0]}" "tinyllama" "model name"
    is "${lines[1]}" "   Path: .*store/ollama/library/tinyllama/.*" "model path"
    is "${lines[2]}" "   Registry: ollama" "model registry"
    is "${lines[3]}" "   Format: GGUF" "model format"
    is "${lines[4]}" "   Version: 3" "model format version"
    is "${lines[5]}" "   Endianness: little" "model endianness"
    is "${lines[6]}" "   Metadata: 23 entries" "# of metadata entries"
    is "${lines[7]}" "   Tensors: 201 entries" "# of tensor entries"
}

# bats test_tags=distro-integration
@test "ramalama inspect GGUF model with --all" {
    run_ramalama inspect --all tiny

    is "${lines[0]}" "tinyllama" "model name"
    is "${lines[1]}" "   Path: .*store/ollama/library/tinyllama/.*" "model path"
    is "${lines[2]}" "   Registry: ollama" "model registry"
    is "${lines[3]}" "   Format: GGUF" "model format"
    is "${lines[4]}" "   Version: 3" "model format version"
    is "${lines[5]}" "   Endianness: little" "model endianness"
    is "${lines[6]}" "   Metadata: " "metadata header"
    is "${lines[7]}" "      general.architecture: llama" "metadata general.architecture"
}

# bats test_tags=distro-integration
@test "ramalama inspect safetensors model" {
    ST_MODEL="https://huggingface.co/LiheYoung/depth-anything-small-hf/resolve/main/model.safetensors"

    run_ramalama pull $ST_MODEL
    run_ramalama inspect $ST_MODEL

    is "${lines[0]}" "model.safetensors" "model name"
    is "${lines[1]}" "   Path: .*store/https/huggingface.co/.*" "model path"
    is "${lines[2]}" "   Registry: https" "model registry"
    is "${lines[3]}" "   Format: pt" "model format"
    is "${lines[4]}" "   Header: 288 entries" "# of metadata entries"
}

# bats test_tags=distro-integration
@test "ramalama inspect safetensors model with --all" {
    ST_MODEL="https://huggingface.co/LiheYoung/depth-anything-small-hf/resolve/main/model.safetensors"

    run_ramalama inspect --all $ST_MODEL

    is "${lines[0]}" "model.safetensors" "model name"
    is "${lines[1]}" "   Path: .*store/https/huggingface.co/.*" "model path"
    is "${lines[2]}" "   Registry: https" "model registry"
    is "${lines[3]}" "   Format: pt" "model format"
    is "${lines[4]}" "   Header: " "metadata header"
    is "${lines[5]}" "      __metadata__: {'format': 'pt'}" "metadata"

    run_ramalama rm $ST_MODEL
}

# vim: filetype=sh
