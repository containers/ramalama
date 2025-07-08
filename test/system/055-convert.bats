#!/usr/bin/env bats

load helpers

# bats test_tags=distro-integration
@test "ramalama convert basic" {
   if is_container; then
	run_ramalama 2 convert
	is "$output" ".*ramalama convert: error: the following arguments are required: SOURCE, TARGET"
	run_ramalama 2 convert tiny
	is "$output" ".*ramalama convert: error: the following arguments are required: TARGET"
	run_ramalama 1 convert bogus foobar
	is "$output" "Error: Manifest for bogus:latest was not found in the Ollama registry"
   else
	run_ramalama 22 convert tiny quay.io/ramalama/foobar
	is "$output" "Error: convert command cannot be run with the --nocontainer option."
   fi
}

@test "ramalama convert file to image" {
    skip_if_nocontainer
    echo "hello" > $RAMALAMA_TMPDIR/aimodel
    run_ramalama convert file://$RAMALAMA_TMPDIR/aimodel foobar
    run_ramalama list
    is "$output" ".*foobar:latest"
    run_ramalama rm foobar
    assert "$output" !~ ".*foobar" "image was removed"

    run_ramalama convert file://$RAMALAMA_TMPDIR/aimodel oci://foobar
    run_ramalama list
    is "$output" ".*foobar:latest"
    run_ramalama 22 convert oci://foobar oci://newimage
    is "$output" "Error: converting from an OCI based image oci://foobar is not supported"

    run_ramalama rm foobar
    run_ramalama list
    assert "$output" !~ ".*foobar" "image was removed"

    run_ramalama 22 convert file://$RAMALAMA_TMPDIR/aimodel ollama://foobar
    is "$output" "Error: ollama://foobar invalid: Only OCI Model types supported" "verify oci image"

    podman image prune --force
}

@test "ramalama convert tiny to image" {
    skip_if_nocontainer
    skip_if_docker
    run_ramalama pull tiny
    run_ramalama convert tiny oci://quay.io/ramalama/tiny
    run_ramalama list
    is "$output" ".*ramalama/tiny:latest"
#    FIXME:  This test will work on all podman 5.3 and greater clients.
#    right now Ubuntu test suite is stuck on podman 5.0.3 Ubuntu 24.10 support
#    it bug github is stuck on 24.04.  Should change when 25.04 is released
#    if is_container and not_docker; then
#       cname=c_$(safename)
#       run_podman version
#       run_ramalama serve -n ${cname} -d quay.io/ramalama/tiny
#       run_ramalama stop ${cname}
#    fi
    run_ramalama rm quay.io/ramalama/tiny
    run_ramalama list
    assert "$output" !~ ".*quay.io/ramalama/tiny" "image was removed"

    run_ramalama convert ollama://tinyllama oci://quay.io/ramalama/tinyllama
    run_ramalama list
    is "$output" ".*quay.io/ramalama/tinyllama:latest"
    run_ramalama rm quay.io/ramalama/tinyllama
    run_ramalama list
    assert "$output" !~ ".*ramalama/tinyllama" "image was removed"

    podman image prune --force
}

@test "ramalama convert tiny to GGUF image" {
    skip_if_nocontainer
    skip_if_docker
    run_ramalama pull hf://TinyLlama/TinyLlama-1.1B-Chat-v1.0
    run_ramalama convert --gguf Q4_0 hf://TinyLlama/TinyLlama-1.1B-Chat-v1.0 oci://quay.io/ramalama/tiny-q4-0
    run_ramalama list
    is "$output" ".*ramalama/tiny-q4-0:latest"
#    FIXME:  This test will work on all podman 5.3 and greater clients.
#    right now Ubuntu test suite is stuck on podman 5.0.3 Ubuntu 24.10 support
#    it bug github is stuck on 24.04.  Should change when 25.04 is released
#    if is_container and not_docker; then
#       cname=c_$(safename)
#       run_podman version
#       run_ramalama serve -n ${cname} -d quay.io/ramalama/tiny-q4-0
#       run_ramalama stop ${cname}
#    fi
    run_ramalama rm quay.io/ramalama/tiny-q4-0
    run_ramalama list
    assert "$output" !~ ".*quay.io/ramalama/tiny-q4-0" "image was removed"

    podman image prune --force
}

# vim: filetype=sh
