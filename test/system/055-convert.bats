#!/usr/bin/env bats

load helpers

# bats test_tags=distro-integration
@test "ramalama convert basic" {
    skip_if_darwin
    run_ramalama 2 convert
    is "$output" ".*ramalama convert: error: the following arguments are required: SOURCE, TARGET"
    run_ramalama 2 convert tiny
    is "$output" ".*ramalama convert: error: the following arguments are required: TARGET"
    run_ramalama 1 convert bogus foobar
    is "$output" "Error: bogus does not exist"
}

@test "ramalama convert file to image" {
    skip_if_darwin
    echo "hello" > $RAMALAMA_TMPDIR/aimodel
    run_ramalama convert $RAMALAMA_TMPDIR/aimodel foobar
    run_ramalama list
    is "$output" ".*foobar:latest"
    run_ramalama rm foobar
    assert "$output" !~ ".*foobar" "image was removed"

    run_ramalama convert $RAMALAMA_TMPDIR/aimodel oci://foobar
    run_ramalama list
    is "$output" ".*foobar:latest"
    run_ramalama rm foobar
    run_ramalama list
    assert "$output" !~ ".*foobar" "image was removed"

    run_ramalama 22 convert $RAMALAMA_TMPDIR/aimodel ollama://foobar
    is "$output" "Error: ollama://foobar invalid: Only OCI Model types supported" "verify oci image"

    podman image prune --force
}

@test "ramalama convert tiny to image" {
    skip_if_darwin
    run_ramalama pull tiny
    run_ramalama convert tiny oci://ramalama/tiny
    run_ramalama list
    is "$output" ".*ramalama/tiny:latest"
    run_ramalama rm ramalama/tiny
    run_ramalama list
    assert "$output" !~ ".*ramalama/tiny" "image was removed"

    run_ramalama convert ollama://tinyllama oci://ramalama/tiny
    run_ramalama list
    is "$output" ".*ramalama/tiny:latest"
    run_ramalama rm ramalama/tiny
    run_ramalama list
    assert "$output" !~ ".*ramalama/tiny" "image was removed"

    podman image prune --force
}



# vim: filetype=sh
