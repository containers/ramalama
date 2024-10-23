#!/usr/bin/env bats

load helpers

# bats test_tags=distro-integration
@test "ramalama pull no model" {
    run_ramalama 2 pull
    is "$output" ".*ramalama pull: error: the following arguments are required: MODEL" "MODEL should be required"
}

# bats test_tags=distro-integration
@test "ramalama pull ollama" {
    run_ramalama pull tiny
    run_ramalama rm tiny
    run_ramalama pull ollama://tinyllama
    run_ramalama list
    is "$output" ".*ollama://tinyllama" "image was actually pulled locally"

    RAMALAMA_TRANSPORT=ollama run_ramalama pull tinyllama:1.1b
    run_ramalama pull ollama://tinyllama:1.1b
    run_ramalama list
    is "$output" ".*ollama://tinyllama:1.1b" "image was actually pulled locally"
    run_ramalama rm ollama://tinyllama ollama://tinyllama:1.1b
}

# bats test_tags=distro-integration
@test "ramalama pull huggingface" {
    run_ramalama pull hf://afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k.gguf
    run_ramalama list
    is "$output" ".*afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k" "image was actually pulled locally"
    run_ramalama rm hf://afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k.gguf

    run_ramalama pull huggingface://afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k.gguf
    run_ramalama list
    is "$output" ".*afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k" "image was actually pulled locally"
    run_ramalama rm huggingface://afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k.gguf

    RAMALAMA_TRANSPORT=huggingface run_ramalama pull afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k.gguf
    run_ramalama list
    is "$output" ".*afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k" "image was actually pulled locally"
    run_ramalama rm huggingface://afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k.gguf
}

# bats test_tags=distro-integration
@test "ramalama pull oci" {
    run_ramalama pull oci://quay.io/mmortari/gguf-py-example:v1
    run_ramalama list
    is "$output" ".*quay.io/mmortari/gguf-py-example" "OCI image was actually pulled locally"
    run_ramalama rm oci://quay.io/mmortari/gguf-py-example:v1

    RAMALAMA_TRANSPORT=oci run_ramalama pull quay.io/mmortari/gguf-py-example:v1
    run_ramalama list
    is "$output" ".*quay.io/mmortari/gguf-py-example" "OCI image was actually pulled locally"
    run_ramalama rm oci://quay.io/mmortari/gguf-py-example:v1
}

# vim: filetype=sh
