#!/usr/bin/env bats

load helpers
load helpers.registry
load setup_suite

# bats test_tags=distro-integration
@test "ramalama inspect GGUF model" {
    MODEL=c_$(safename)
    run_ramalama 22 inspect ${MODEL}
    is "$output" "Error: No ref file found for '${MODEL}'. Please pull model."
    
    run_ramalama pull ollama://tinyllama
    run_ramalama inspect ollama://tinyllama

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
    run_ramalama pull ollama://tinyllama
    run_ramalama inspect --all ollama://tinyllama

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
@test "ramalama inspect GGUF model with --get" {
    run_ramalama pull ollama://tinyllama

    run_ramalama inspect --get general.architecture ollama://tinyllama
    is "$output" "llama"

    run_ramalama inspect --get general.name ollama://tinyllama
    is "$output" "TinyLlama"
}

# bats test_tags=distro-integration
@test "ramalama inspect GGUF model with --get all" {
    run_ramalama pull ollama://tinyllama

    run_ramalama inspect --get all ollama://tinyllama
    is "${lines[0]}" "general.architecture: llama" "check for general.architecture"
    is "${lines[1]}" "general.file_type: 2" "check for general.file_type"
    is "${lines[2]}" "general.name: TinyLlama" "check for general.name"
    is "${lines[3]}" "general.quantization_version: 2" "check for general.quantization_version"
    is "${lines[4]}" "llama.attention.head_count: 32" "check for llama.attention.head_count"
    is "${lines[5]}" "llama.attention.head_count_kv: 4" "check for llama.attention.head_count_kv"
    is "${lines[6]}" "llama.attention.layer_norm_rms_epsilon: 9.999999747378752e-06" "check for llama.attention.layer_norm_rms_epsilon"
    is "${lines[7]}" "llama.block_count: 22" "check for llama.block_count"
    is "${lines[8]}" "llama.context_length: 2048" "check for llama.context_length"
    is "${lines[9]}" "llama.embedding_length: 2048" "check for llama.embedding_length"
    is "${lines[10]}" "llama.feed_forward_length: 5632" "check for llama.feed_forward_length"
    is "${lines[11]}" "llama.rope.dimension_count: 64" "check for llama.rope.dimension_count"
    is "${lines[12]}" "llama.rope.freq_base: 10000.0" "check for llama.rope.freq_base"
    is "${lines[13]}" "tokenizer.ggml.bos_token_id: 1" "check for tokenizer.ggml.bos_token_id"
    is "${lines[14]}" "tokenizer.ggml.eos_token_id: 2" "check for tokenizer.ggml.eos_token_id"
    is "${lines[15]}" "tokenizer.ggml.model: llama" "check for tokenizer.ggml.model"
    is "${lines[16]}" "tokenizer.ggml.padding_token_id: 2" "check for tokenizer.ggml.padding_token_id"
    is "${lines[17]}" "tokenizer.ggml.unknown_token_id: 0" "check for tokenizer.ggml.unknown_token_id"
}

# bats test_tags=distro-integrationfields
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
