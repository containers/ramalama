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
    run_ramalama pull https://ollama.com/library/smollm:135m
    run_ramalama list
    is "$output" ".*https://ollama.com/library/smollm:135m" "image was actually pulled locally"

    RAMALAMA_TRANSPORT=ollama run_ramalama pull smollm:360m
    run_ramalama pull ollama://smollm:360m
    run_ramalama list
    is "$output" ".*ollama://library/smollm:360m" "image was actually pulled locally"
    run_ramalama rm ollama://smollm:135m ollama://smollm:360m

    random_image_name=i_$(safename)
    run_ramalama 1 -q pull ${random_image_name}
    is "$output" "Error: Manifest for ${random_image_name}:latest was not found in the Ollama registry"
}

# bats test_tags=distro-integration
@test "ramalama pull ollama cache" {
    skip_if_no_ollama

    ollama serve &
    sleep 3
    ollama pull tinyllama
    run_ramalama pull tiny
    run_ramalama rm tiny
    ollama rm tinyllama

    ollama pull smollm:135m
    run_ramalama pull https://ollama.com/library/smollm:135m
    run_ramalama list
    is "$output" ".*https://ollama.com/library/smollm:135m" "image was actually pulled locally from ollama cache"

    ollama pull smollm:360m
    RAMALAMA_TRANSPORT=ollama run_ramalama pull smollm:360m
    run_ramalama pull ollama://smollm:360m
    run_ramalama list
    is "$output" ".*ollama://library/smollm:360m" "image was actually pulled locally from ollama cache"
    run_ramalama rm https://ollama.com/library/smollm:135m ollama://smollm:360m
    ollama rm smollm:135m smollm:360m

    random_image_name=i_$(safename)
    run_ramalama 1 -q pull ${random_image_name}
    is "$output" "Error: Manifest for ${random_image_name}:latest was not found in the Ollama registry"

    pkill ollama
}

# bats test_tags=distro-integration
@test "ramalama pull huggingface" {
    run_ramalama pull hf://Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf
    run_ramalama list
    is "$output" ".*Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS" "image was actually pulled locally"
    run_ramalama rm hf://Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf

    run_ramalama pull huggingface://Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf
    run_ramalama list
    is "$output" ".*Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS" "image was actually pulled locally"
    run_ramalama rm huggingface://Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf

    RAMALAMA_TRANSPORT=huggingface run_ramalama pull Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf
    run_ramalama list
    is "$output" ".*Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS" "image was actually pulled locally"
    run_ramalama rm huggingface://Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf

    skip_if_no_hf-cli
    run_ramalama pull hf://TinyLlama/TinyLlama-1.1B-Chat-v1.0
    run_ramalama list
    is "$output" ".*TinyLlama/TinyLlama-1.1B-Chat-v1.0" "image was actually pulled locally"
    run_ramalama rm huggingface://TinyLlama/TinyLlama-1.1B-Chat-v1.0

    run_ramalama pull hf://ggml-org/SmolVLM-256M-Instruct-GGUF
    run_ramalama list
    is "$output" ".*ggml-org/SmolVLM-256M-Instruct-GGUF" "image was actually pulled locally"
    run_ramalama rm huggingface://ggml-org/SmolVLM-256M-Instruct-GGUF

    run_ramalama pull hf://ggml-org/SmolVLM-256M-Instruct-GGUF:Q8_0
    run_ramalama list
    is "$output" ".*ggml-org/SmolVLM-256M-Instruct-GGUF:Q8_0" "image was actually pulled locally"
    run_ramalama rm huggingface://ggml-org/SmolVLM-256M-Instruct-GGUF:Q8_0
}

# bats test_tags=distro-integration
@test "ramalama pull huggingface tag multiple references" {
    run_ramalama pull hf://ggml-org/SmolVLM-256M-Instruct-GGUF
    run_ramalama list
    is "$output" ".*ggml-org/SmolVLM-256M-Instruct-GGUF" "image was actually pulled locally"
    run_ramalama --debug pull hf://ggml-org/SmolVLM-256M-Instruct-GGUF:Q8_0
    is "$output" ".*Using cached blob" "cached blob was used"
    run_ramalama list
    is "$output" ".*ggml-org/SmolVLM-256M-Instruct-GGUF:Q8_0" "reference was created to existing image"
    run_ramalama --debug rm huggingface://ggml-org/SmolVLM-256M-Instruct-GGUF
    is "$output" ".*Not removing snapshot" "snapshot with remaining reference was not deleted"
    run_ramalama --debug rm huggingface://ggml-org/SmolVLM-256M-Instruct-GGUF:Q8_0
    is "$output" ".*Snapshot removed" "snapshot with no remaining references was deleted"
}

# bats test_tags=distro-integration
@test "ramalama pull huggingface-cli cache" {
    skip_if_no_hf-cli
    huggingface-cli download Felladrin/gguf-smollm-360M-instruct-add-basics smollm-360M-instruct-add-basics.IQ2_XXS.gguf

    run_ramalama pull hf://Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf
    run_ramalama list
    is "$output" ".*Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS" "image was actually pulled locally from hf-cli cache"
    run_ramalama rm hf://Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf

    run_ramalama pull huggingface://Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf
    run_ramalama list
    is "$output" ".*Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS" "image was actually pulled locally from hf-cli cache"
    run_ramalama rm huggingface://Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf

    RAMALAMA_TRANSPORT=huggingface run_ramalama pull Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf
    run_ramalama list
    is "$output" ".*Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS" "image was actually pulled locally from hf-cli cache"
    run_ramalama rm huggingface://Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf

    rm -rf ~/.cache/huggingface/hub/models--Felladrin--gguf-smollm-360M-instruct-add-basics
}

# bats test_tags=distro-integration
@test "ramalama pull oci" {
    if is_container; then
        model=oci://quay.io/ramalama/smollm:135m
        run_ramalama pull ${model}
        run_ramalama list
        is "$output" ".*${model}.*" "image was actually pulled locally"
        run_ramalama --nocontainer list
        assert "$output" !~ ".*${model}" "model is not in list"
        run_ramalama rm ${model}
    else
        run_ramalama 22 pull oci://quay.io/ramalama/smollm:135m
	is "$output" "Error: OCI containers cannot be used with the --nocontainer option."
    fi

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
      run_ramalama pull $file_url
      run_ramalama list
      is "$output" ".*$file_url" "URL exists"
      run_ramalama rm $file_url
      run_ramalama list
      assert "$output" !~ ".*file_url" "URL no longer exists"

      https_url=https://github.com/containers/ramalama/blob/main/README.md
      run_ramalama pull $https_url
      run_ramalama list
      expected_url="${https_url}":main
      expected_url="$(sed "s/blob\/main\///" <<< $expected_url)"
      is "$output" ".*$expected_url" "URL exists"
      run_ramalama rm $https_url
      run_ramalama list
      assert "$output" !~ ".*$expected_url" "URL no longer exists"
}

@test "ramalama file URL" {
      model=$RAMALAMA_TMPDIR/mymodel.gguf
      touch $model
      url=file://${model}
      run_ramalama pull $url
      run_ramalama list
      is "$output" ".*$url" "URL exists"
      
      # test if original model file is removed, nothing blows up
      rm ${model}
      run_ramalama list
      is "$output" ".*$url" "URL exists"

      run_ramalama rm $url
      run_ramalama list
      assert "$output" !~ ".*$url" "URL no longer exists"
}

@test "ramalama use registry" {
    skip_if_darwin
    skip_if_docker
    skip_if_nocontainer
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
    run_ramalama push --authfile=$authfile --tls-verify=false tiny $registry/tiny
    run_ramalama push --authfile=$authfile --tls-verify=false --type car tiny oci://$registry/tiny-car

    tmpfile=${RAMALAMA_TMPDIR}/mymodel
    random=$(random_string 30)
    echo $random > $tmpfile
    run_ramalama push --authfile=$authfile --tls-verify=false --type raw file://$tmpfile $registry/mymodel


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
