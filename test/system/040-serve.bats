#!/usr/bin/env bats

load helpers
load helpers.registry
load setup_suite

verify_begin=".*run --rm"

@test "ramalama --dryrun serve basic output" {
    model=m_$(safename)

    if is_container; then
	run_ramalama -q --dryrun serve ${model}
	is "$output" "${verify_begin}.*" "dryrun correct"
	is "$output" ".*--name ramalama_.*" "dryrun correct"
	is "$output" ".*${model}" "verify model name"
	is "$output" ".*--cache-reuse 256" "cache"
	assert "$output" !~ ".*--no-webui"

	run_ramalama --dryrun serve --webui off ${model}
	assert "$output" =~ ".*--no-webui"

	run_ramalama -q --dryrun serve --name foobar ${model}
	is "$output" ".*--name foobar .*" "dryrun correct with --name"
	assert "$output" !~ ".*--network" "--network is not part of the output"
	is "$output" ".*--host 0.0.0.0" "verify host 0.0.0.0 is added when run within container"
	is "$output" ".*${model}" "verify model name"
	assert "$output" !~ ".*--seed" "assert seed does not show by default"

	run_ramalama -q --dryrun serve --network bridge --host 127.1.2.3 --name foobar ${model}
	assert "$output" =~ "--network bridge.*--host 127.1.2.3" "verify --host is modified when run within container"
	is "$output" ".*${model}" "verify model name"
	is "$output" ".*--temp 0.8" "verify temp is set"
	assert "$output" !~ ".*-t " "assert -t not present"
	assert "$output" !~ ".*-i " "assert -t not present"

	run_ramalama -q --dryrun serve --temp 0.1 ${model}
	is "$output" ".*--temp 0.1" "verify temp is set"

	RAMALAMA_CONFIG=/dev/null run_ramalama -q --dryrun serve --seed 1234 ${model}
	is "$output" ".*--seed 1234" "verify seed is set"
	if not_docker; then
	    is "$output" ".*--pull newer" "verify pull is newer"
	fi
	assert "$output" =~ ".*--cap-drop=all" "verify --cap-add is present"
	assert "$output" =~ ".*no-new-privileges" "verify --no-new-privs is not present"

	run_ramalama -q --dryrun serve ${model}
	is "$output" ".*--pull missing" "verify test default pull is missing"

	run_ramalama -q --dryrun serve --pull never ${model}
	is "$output" ".*--pull never" "verify pull is never"

	run_ramalama 2 -q --dryrun serve --pull=bogus ${model}
	is "$output" ".*error: argument --pull: invalid choice: 'bogus'" "verify pull can not be bogus"

	run_ramalama -q --dryrun serve --privileged ${model}
	is "$output" ".*--privileged" "verify --privileged is set"
	assert "$output" != ".*--cap-drop=all" "verify --cap-add is not present"
	assert "$output" != ".*no-new-privileges" "verify --no-new-privs is not present"
    else
	run_ramalama -q --dryrun serve ${model}
	assert "$output" =~ ".*--host 0.0.0.0" "Outside container sets host to 0.0.0.0"
	is "$output" ".*--cache-reuse 256" "should use cache"
	if is_darwin; then
	   is "$output" ".*--flash-attn" "use flash-attn on Darwin metal"
	fi

	run_ramalama -q --dryrun serve --seed abcd --host 127.0.0.1 ${model}
	assert "$output" =~ ".*--host 127.0.0.1" "Outside container overrides host to 127.0.0.1"
	assert "$output" =~ ".*--seed abcd" "Verify seed is set"
	run_ramalama 1 --nocontainer serve --name foobar tiny
	is "${lines[0]}"  "Error: --nocontainer and --name options conflict. The --name option requires a container." "conflict between nocontainer and --name line"
    fi

    run_ramalama -q --dryrun serve --runtime-args="--foo -bar" ${model}
    assert "$output" =~ ".*--foo" "--foo passed to runtime"
    assert "$output" =~ ".*-bar" "-bar passed to runtime"

    run_ramalama -q --dryrun serve --runtime-args="--foo='a b c'" ${model}
    assert "$output" =~ ".*--foo=a b c" "argument passed to runtime with spaces"

    run_ramalama 1 -q --dryrun serve --runtime-args="--foo='a b c" ${model}
    assert "$output" =~ "No closing quotation" "error for improperly quoted runtime arguments"

    run_ramalama 1 serve MODEL
    assert "$output" =~ "Error: Manifest for MODEL:latest was not found in the Ollama registry"
}

@test "ramalama --detach serve" {
    skip_if_nocontainer

    model=m_$(safename)

    run_ramalama -q --dryrun serve --detach ${model}
    is "$output" ".*-d .*" "dryrun correct"
    is "$output" ".*--name ramalama_.*" "serve in detach mode"

    run_ramalama -q --dryrun serve -d ${model}
    is "$output" ".*-d .*" "dryrun correct"
    is "$output" ".*--name ramalama_.*" "dryrun correct"

    run_ramalama stop --all
}

@test "ramalama serve and stop" {
    skip "Seems to cause race conditions"
    skip_if_nocontainer

    model=ollama://smollm:135m
    container1=c_$(safename)
    container2=c_$(safename)

    run_ramalama serve --name ${container1} --detach ${model}
    cid="$output"
    run_ramalama info
    conmon=$(jq .Engine <<< $output)

    run -0 ${conman} inspect1 $cid

    run_ramalama ps
    is "$output" ".*${container1}" "list correct for container1"

    run_ramalama containers --noheading
    is "$output" ".*${container1}" "list correct for container1"
    run_ramalama stop ${container1}

    run_ramalama serve --name ${container2} -d ${model}
    cid="$output"
    run_ramalama containers -n
    is "$output" ".*${cid:0:10}" "list correct with cid"
    run_ramalama ps --noheading --no-trunc
    is "$output" ".*${container2}" "list correct with cid and no heading"
    run_ramalama stop ${cid}
    run_ramalama ps --noheading
    is "$output" "" "all containers gone"
}

@test "ramalama --detach serve multiple" {
    skip "Seems to cause race conditions"
    skip_if_nocontainer

    model=ollama://smollm:135m
    container=c_$(safename)
    port1=8100
    port2=8200

    run_ramalama stop --all

    run_ramalama serve -p ${port1} --detach ${model}
    cid="$output"

    run_ramalama serve -p ${port2} --detach ${model}
    cid="$output"

    run_ramalama containers --noheading
    is ${#lines[@]} 2 "two containers should be running"

    run_ramalama stop --all
    run_ramalama containers -n
    is "$output" "" "no more containers should exist"
}

@test "ramalama stop failures" {
    skip_if_nocontainer
    name=m_$(safename)
    run_ramalama 22 stop
    is "$output" "Error: must specify a container name" "name required"

    run_ramalama ? stop ${name}
    is "$output" "Error.*such container.*" "missing container"

    run_ramalama stop --ignore ${name}
    is "$output" "" "ignore missing"

    run_ramalama 22 stop --all ${name}
    is "$output" "Error: specifying --all and container name, ${name}, not allowed" "list correct"
}

@test "ramalama serve --generate=quadlet" {
    model="smollm"
    model_quant="$model:135m"
    quadlet="$model.container"
    name=c_$(safename)
    run_ramalama pull $model_quant
    run_ramalama -q serve --port 1234 --generate=quadlet $model
    is "$output" "Generating quadlet file: $quadlet" "generate $quadlet"

    run cat $quadlet
    is "$output" ".*PublishPort=1234:1234" "PublishPort should match"
    is "$output" ".*Exec=.*llama-server --port 1234 --model .*" "Exec line should be correct"
    is "$output" ".*Mount=type=bind,.*$model" "Mount line should be correct"

    HIP_VISIBLE_DEVICES=99 run_ramalama -q serve --port 1234 --generate=quadlet $model
    is "$output" "Generating quadlet file: $quadlet" "generate $quadlet"

    run cat $quadlet
    is "$output" ".*Environment=HIP_VISIBLE_DEVICES=99" "Should contain env property"

    rm $quadlet
    run_ramalama 2 serve --name=${name} --port 1234 --generate=bogus $model
    is "$output" ".*error: argument --generate: invalid choice: .*bogus.* (choose from.*quadlet.*kube.*quadlet/kube.*)" "Should fail"
}

@test "ramalama serve --generate=quadlet and --generate=kube with OCI" {
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

    ociimage=$registry/tiny:latest
    for modeltype in "" "--type=car" "--type=raw"; do
	name=c_$(safename)
	run_ramalama push $modeltype --authfile=$authfile --tls-verify=false tiny oci://${ociimage}
	run_ramalama serve --authfile=$authfile --tls-verify=false --name=${name} --port 1234 --generate=quadlet oci://${ociimage}
	is "$output" ".*Generating quadlet file: ${name}.container" "generate .container file"
	is "$output" ".*Generating quadlet file: ${name}.volume" "generate .volume file"
	is "$output" ".*Generating quadlet file: ${name}.image" "generate .image file"

	run cat $name.container
	is "$output" ".*PublishPort=1234:1234" "PublishPort should match"
	is "$output" ".*ContainerName=${name}" "Quadlet should have ContainerName field"
	is "$output" ".*Exec=.*llama-server --port 1234 --model .*" "Exec line should be correct"
	is "$output" ".*Mount=type=image,source=${ociimage},destination=/mnt/models,subpath=/models,readwrite=false" "Volume line should be correct"

	if is_container; then
	   run cat $name.volume
	   is "$output" ".*Driver=image" "Driver Image"
	   is "$output" ".*Image=$name.image" "Image should exist"

	   run cat $name.image
	   is "$output" ".*Image=${ociimage}" "Image should match"
	fi

	run_ramalama list
	is "$output" ".*${ociimage}" "Image should match"

	rm $name.container
	if is_container; then
	   rm $name.volume
	   rm $name.image
	fi

    run_ramalama rm oci://${ociimage}
    done
    stop_registry
    skip "vLLM can't serve GGUFs, needs tiny safetensor"

	run_ramalama --runtime=vllm serve --authfile=$authfile --tls-verify=false --name=${name} --port 1234 --generate=kube oci://${ociimage}
	is "$output" ".*Generating Kubernetes YAML file: ${name}.yaml" "generate .yaml file"

	run_ramalama --runtime=vllm serve --authfile=$authfile --tls-verify=false --name=${name} --port 1234 --generate=quadlet/kube oci://${ociimage}
	is "$output" ".*Generating Kubernetes YAML file: ${name}.yaml" "generate .yaml file"
	is "$output" ".*Generating quadlet file: ${name}.kube" "generate .kube file"


	run cat $name.yaml
	is "$output" ".*command: \[\"--port\"\]" "command is correct"
	is "$output" ".*args: \['1234', '--model', '/mnt/models/model.file', '--max_model_len', '2048'\]" "args are correct"

	is "$output" ".*reference: ${ociimage}" "AI image should be created"
	is "$output" ".*pullPolicy: IfNotPresent" "pullPolicy should exist"

    rm $name.yaml
}


@test "ramalama serve --generate=kube" {
    model="smollm"
    model_quant="$model:135m"
    name=c_$(safename)
    run_ramalama pull $model_quant
    run_ramalama serve --name=${name} --port 1234 --generate=kube $model_quant
    is "$output" ".*Generating Kubernetes YAML file: ${name}.yaml" "generate .yaml file"

    run cat $name.yaml
    is "$output" ".*command: \[\".*serve.*\"\]" "Should command"
    is "$output" ".*containerPort: 1234" "Should container container port"

    HIP_VISIBLE_DEVICES=99 run_ramalama serve --name=${name} --port 1234 --generate=kube $model_quant
    is "$output" ".*Generating Kubernetes YAML file: ${name}.yaml" "generate .yaml file"

    run cat $name.yaml
    is "$output" ".*env:" "Should contain env property"
    is "$output" ".*name: HIP_VISIBLE_DEVICES" "Should contain env name"
    is "$output" ".*value: 99" "Should contain env value"

    run_ramalama serve --name=${name} --port 1234 --generate=quadlet/kube $model_quant
    is "$output" ".*Generating Kubernetes YAML file: ${name}.yaml" "generate .yaml file"
    is "$output" ".*Generating quadlet file: ${name}.kube" "generate .kube file"

    run cat $name.yaml
    is "$output" ".*command: \[\".*serve.*\"\]" "Should command"
    is "$output" ".*containerPort: 1234" "Should container container port"

    HIP_VISIBLE_DEVICES=99 run_ramalama serve --name=${name} --port 1234 --generate=quadlet/kube $model_quant
    is "$output" ".*Generating Kubernetes YAML file: ${name}.yaml" "generate .yaml file"

    run cat $name.yaml
    is "$output" ".*env:" "Should contain env property"
    is "$output" ".*name: HIP_VISIBLE_DEVICES" "Should contain env name"
    is "$output" ".*value: 99" "Should contain env value"

    run cat $name.kube
    is "$output" ".*Yaml=$name.yaml" "Should container container port"
    rm $name.kube
    rm $name.yaml
}

@test "ramalama serve --generate=kube:/tmp" {
    model=tiny
    name=c_$(safename)
    run_ramalama pull ${model}
    run_ramalama serve --name=${name} --port 1234 --generate=kube:/tmp ${model}
    is "$output" ".*Generating Kubernetes YAML file: ${name}.yaml" "generate .yaml file"

    run cat /tmp/$name.yaml
    is "$output" ".*command: \[\".*serve.*\"\]" "Should command"
    is "$output" ".*containerPort: 1234" "Should container container port"

    rm /tmp/$name.yaml
}

@test "ramalama serve --api llama-stack --generate=kube:/tmp" {
    skip_if_docker
    skip_if_nocontainer
    model=tiny
    name=c_$(safename)
    run_ramalama pull ${model}
    run_ramalama serve -d --name=${name} --api llama-stack --dri off --port 1234 ${model}
    is "$output" ".*Llama Stack RESTAPI: http://localhost:1234" "reveal llama stack url"
    is "$output" ".*OpenAI RESTAPI: http://localhost:1234/v1/openai" "reveal openai url"

### FIXME llama-stack image is currently broken.
    # Health check: wait for service to be responsive on http://localhost:1234
#    for i in {1..10}; do
#    	if curl -sSf http://localhost:1234/models > /dev/null; then
#            echo "Service is responsive on http://localhost:1234/v1/openai/models"
#            break
#        fi
#        sleep 1
#    done
#    if ! curl -sSf http://localhost:1234/v1/openai/models > /dev/null; then
#        echo "ERROR: Service did not become responsive on http://localhost:1234" >&2
#        run_ramalama stop ${name}
#        exit 1
#    fi
    run_ramalama ps
    run_ramalama stop ${name}

    run_ramalama serve --name=${name} --api llama-stack --port 1234 --generate=kube:/tmp ${model}
    is "$output" ".*Generating Kubernetes YAML file: ${name}.yaml" "generate .yaml file"

    run cat /tmp/$name.yaml
    is "$output" ".*llama-server" "Should command"
    is "$output" ".*hostPort: 1234" "Should container container port"
    is "$output" ".*quay.io/ramalama/llama-stack" "Should container llama-stack"
    rm /tmp/$name.yaml
}

@test "ramalama serve --image bogus" {
    skip_if_nocontainer
    skip_if_darwin
    skip_if_docker
    run_ramalama 125 --image bogus serve --pull=never tiny
    is "$output" "Error: bogus: image not known"

    run_ramalama 125 --image bogus1 serve --rag quay.io/ramalama/testrag --pull=never tiny
    is "$output" ".*Error: bogus1: image not known"
}

@test "ramalama serve with rag" {
    skip_if_nocontainer
    skip_if_darwin
    skip_if_docker
    run_ramalama ? stop ${name}
    run_ramalama ? --dryrun serve --rag quay.io/ramalama/rag --pull=never tiny
    is "$output" ".*Error: quay.io/ramalama/rag: image not known"

    run_ramalama --dryrun serve --rag quay.io/ramalama/testrag --pull=never tiny
    is "$output" ".*quay.io/ramalama/.*-rag:"

    run_ramalama --dryrun --image quay.io/ramalama/ramalama:1.0 serve --rag quay.io/ramalama/testrag --pull=never tiny
    is "$output" ".*quay.io/ramalama/ramalama:1.0"
}

# vim: filetype=sh
