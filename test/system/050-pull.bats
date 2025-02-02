#!/usr/bin/env bats

load helpers
load helpers.registry
load setup_suite

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

    random_image_name=i_$(safename)
    run_ramalama 1 pull ${random_image_name}
    is "$output" "Error: ${random_image_name} was not found in the Ollama registry"
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

    run_ramalama pull hf://TinyLlama/TinyLlama-1.1B-Chat-v1.0
    run_ramalama list
    is "$output" ".*TinyLlama/TinyLlama-1.1B-Chat-v1.0" "image was actually pulled locally"
    run_ramalama rm huggingface://TinyLlama/TinyLlama-1.1B-Chat-v1.0
}

# bats test_tags=distro-integration
@test "ramalama pull oci" {
    skip "Waiting for podman artiface support" 
    run_ramalama pull oci://quay.io/mmortari/gguf-py-example:v1
    run_ramalama list
    is "$output" ".*quay.io/mmortari/gguf-py-example" "OCI image was actually pulled locally"
    run_ramalama rm oci://quay.io/mmortari/gguf-py-example:v1

    RAMALAMA_TRANSPORT=oci run_ramalama pull quay.io/mmortari/gguf-py-example:v1
    run_ramalama list
    is "$output" ".*quay.io/mmortari/gguf-py-example" "OCI image was actually pulled locally"
    run_ramalama rm oci://quay.io/mmortari/gguf-py-example:v1
}

@test "ramalama URL" {
      model=$RAMALAMA_TMPDIR/mymodel.gguf
      touch $model
      file_url=file://${model}
      https_url=https://github.com/containers/ramalama/blob/main/README.md

      for url in $file_url $https_url; do
          run_ramalama pull $url
          run_ramalama list
          is "$output" ".*$url" "URL exists"
          run_ramalama rm $url
          run_ramalama list
          assert "$output" !~ ".*$url" "URL no longer exists"
      done
}

@test "ramalama file URL" {
      model=$RAMALAMA_TMPDIR/mymodel.gguf
      touch $model
      url=file://${model}

      run_ramalama pull $url
      run_ramalama list
      is "$output" ".*$url" "URL exists"
      # test if model is removed, nothing blows up
      rm ${model}
      run_ramalama list
      is "$output" ".*$url does not exist" "URL exists"
      run_ramalama rm $url
      run_ramalama list
      assert "$output" !~ ".*$url" "URL no longer exists"
}

@test "ramalama use registry" {
    skip_if_darwin
    skip_if_docker
    local registry=localhost:${PODMAN_LOGIN_REGISTRY_PORT}
    local authfile=$RAMALAMA_TMPDIR/authfile.json

    start_registry
    run_ramalama login --authfile=$authfile \
	--tls-verify=false \
	--username ${PODMAN_LOGIN_USER} \
	--password ${PODMAN_LOGIN_PASS} \
	oci://$registry
    run_ramalama pull tiny
    run_ramalama push --authfile=$authfile --tls-verify=false tiny oci://$registry/tiny
    run_ramalama push --authfile=$authfile --tls-verify=false --type car tiny oci://$registry/tiny-car

    tmpfile=${RAMALAMA_TMPDIR}/mymodel
    random=$(random_string 30)
    echo $random > $tmpfile
    run_ramalama push --authfile=$authfile --tls-verify=false --type raw $tmpfile oci://$registry/mymodel


    run_ramalama list
    is "$output" ".*oci://$registry/tiny" "OCI image exists in list"
    is "$output" ".*oci://$registry/tiny-car" "OCI image exists in list"
    is "$output" ".*oci://$registry/mymodel" "OCI image exists in list"

    run_ramalama rm oci://$registry/tiny
    run_ramalama rm oci://$registry/tiny-car
    run_ramalama rm $registry/mymodel

    run_ramalama list
    assert "$output" !~ ".*oci://$registry/tiny-car" "OCI image does not exist in list"
    assert "$output" !~ ".*oci://$registry/tiny" "OCI image does not exist in list"
    assert "$output" !~ ".*oci://$registry/mymodel" "OCI image does not exist in list"

    run_podman image prune --force

    stop_registry
}

# vim: filetype=sh
