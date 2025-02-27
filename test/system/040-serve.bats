#!/usr/bin/env bats

load helpers
load helpers.registry
load setup_suite

verify_begin=".*run --rm -i --label ai.ramalama --name"

@test "ramalama --dryrun serve basic output" {
    model=m_$(safename)

    if is_container; then
	run_ramalama --dryrun serve ${model}
	is "$output" "${verify_begin} ramalama_.*" "dryrun correct"
	is "$output" ".*${model}" "verify model name"

	run_ramalama --dryrun serve --name foobar ${model}
	is "$output" "${verify_begin} foobar .*" "dryrun correct with --name"
	assert "$output" !~ ".*--network" "--network is not part of the output"
	is "$output" ".*${model}" "verify model name"
	assert "$output" !~ ".*--host" "verify --host not added when run within container"
	assert "$output" !~ ".*--seed" "assert seed does not show by default"

	run_ramalama --dryrun serve --network bridge --host 127.1.2.3 --name foobar ${model}
	is "$output" ".*${model}" "verify model name"
	is "$output" ".*--temp 0.8" "verify temp is set"

	run_ramalama --dryrun serve --temp 0.1 ${model}
	is "$output" ".*--temp 0.1" "verify temp is set"

	run_ramalama --dryrun serve --seed 1234 ${model}
	is "$output" ".*--seed 1234" "verify seed is set"
	if not_docker; then
	   is "$output" ".*--pull=newer" "verify pull is newer"
	fi
	assert "$output" =~ ".*--cap-drop=all" "verify --cap-add is present"
	assert "$output" =~ ".*no-new-privileges" "verify --no-new-privs is not present"

	run_ramalama --dryrun serve --pull=never ${model}
	is "$output" ".*--pull=never" "verify pull is never"

	run_ramalama 2 --dryrun serve --pull=bogus ${model}
	is "$output" ".*error: argument --pull: invalid choice: 'bogus'" "verify pull can not be bogus"

	if is_container; then
	    run_ramalama --dryrun serve --privileged ${model}
	    is "$output" ".*--privileged" "verify --privileged is set"
	    assert "$output" != ".*--cap-drop=all" "verify --cap-add is not present"
	    assert "$output" != ".*no-new-privileges" "verify --no-new-privs is not present"
	fi

	run_ramalama stop --all
    else
	run_ramalama --dryrun serve ${model}
	assert "$output" =~ ".*--host 127.0.0.1" "Outside container sets host to 127.0.0.1"
	run_ramalama --dryrun serve --seed abcd --host 127.0.0.2 ${model}
	assert "$output" =~ ".*--host 127.0.0.2" "Outside container overrides host to 127.0.0.2"
	assert "$output" =~ ".*--seed abcd" "Verify seed is set"
	run_ramalama 1 --nocontainer serve --name foobar tiny
	is "${lines[0]}"  "Error: --nocontainer and --name options conflict. The --name option requires a container." "conflict between nocontainer and --name line"
     fi

    run_ramalama 1 serve MODEL
    is "$output" "Error: MODEL was not found in the Ollama registry"
}

@test "ramalama --detach serve" {
    skip_if_nocontainer

    model=m_$(safename)

    run_ramalama --dryrun serve --detach ${model}
    is "$output" "${verify_begin} ramalama_.*" "serve in detach mode"

    run_ramalama --dryrun serve -d ${model}
    is "$output" "${verify_begin} ramalama_.*" "dryrun correct"

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
    model=tiny
    name=c_$(safename)
    run_ramalama pull ${model}
    run_ramalama serve --port 1234 --generate=quadlet ${model}
    is "$output" "Generating quadlet file: tinyllama.container" "generate tinllama.container"

    run cat tinyllama.container
    is "$output" ".*PublishPort=1234" "PublishPort should match"
    is "$output" ".*Exec=llama-server --port 1234 -m .*" "Exec line should be correct"
    is "$output" ".*Mount=type=bind,.*tinyllama" "Mount line should be correct"

    HIP_SOMETHING=99 run_ramalama serve --port 1234 --generate=quadlet ${model}
    is "$output" "Generating quadlet file: tinyllama.container" "generate tinllama.container"

    run cat tinyllama.container
    is "$output" ".*Environment=HIP_SOMETHING=99" "Should contain env property"

    rm tinyllama.container
    run_ramalama 2 serve --name=${name} --port 1234 --generate=bogus tiny
    is "$output" ".*error: argument --generate: invalid choice: 'bogus' (choose from.*quadlet.*kube.*quadlet/kube.*)" "Should fail"
}

@test "ramalama serve --generate=quadlet and --generate=kube with OCI" {
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

    ociimage=$registry/tiny:latest
    for modeltype in "" "--type=car" "--type=raw"; do
	name=c_$(safename)
	run_ramalama push $modeltype --authfile=$authfile --tls-verify=false tiny oci://${ociimage}
	run_ramalama serve --authfile=$authfile --tls-verify=false --name=${name} --port 1234 --generate=quadlet oci://${ociimage}
	is "$output" ".*Generating quadlet file: ${name}.container" "generate .container file"
	if is_container; then
	   is "$output" ".*Generating quadlet file: ${name}.volume" "generate .volume file"
	   is "$output" ".*Generating quadlet file: ${name}.image" "generate .image file"
	fi

	run cat $name.container
	is "$output" ".*PublishPort=1234" "PublishPort should match"
	is "$output" ".*ContainerName=${name}" "Quadlet should have ContainerName field"
	is "$output" ".*Exec=llama-server --port 1234 -m .*" "Exec line should be correct"
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

	run_ramalama rm oci://${ociimage}
	rm $name.yaml
    done
    stop_registry
}


@test "ramalama serve --generate=kube" {
    model=tiny
    name=c_$(safename)
    run_ramalama pull ${model}
    run_ramalama serve --name=${name} --port 1234 --generate=kube ${model}
    is "$output" ".*Generating Kubernetes YAML file: ${name}.yaml" "generate .yaml file"

    run cat $name.yaml
    is "$output" ".*command: \[\"llama-server\"\]" "Should command"
    is "$output" ".*containerPort: 1234" "Should container container port"

    HIP_SOMETHING=99 run_ramalama serve --name=${name} --port 1234 --generate=kube ${model}
    is "$output" ".*Generating Kubernetes YAML file: ${name}.yaml" "generate .yaml file"

    run cat $name.yaml
    is "$output" ".*env:" "Should contain env property"
    is "$output" ".*name: HIP_SOMETHING" "Should contain env name"
    is "$output" ".*value: 99" "Should contain env value"

    run_ramalama serve --name=${name} --port 1234 --generate=quadlet/kube ${model}
    is "$output" ".*Generating Kubernetes YAML file: ${name}.yaml" "generate .yaml file"
    is "$output" ".*Generating quadlet file: ${name}.kube" "generate .kube file"

    run cat $name.yaml
    is "$output" ".*command: \[\"llama-server\"\]" "Should command"
    is "$output" ".*containerPort: 1234" "Should container container port"

    HIP_SOMETHING=99 run_ramalama serve --name=${name} --port 1234 --generate=quadlet/kube ${model}
    is "$output" ".*Generating Kubernetes YAML file: ${name}.yaml" "generate .yaml file"

    run cat $name.yaml
    is "$output" ".*env:" "Should contain env property"
    is "$output" ".*name: HIP_SOMETHING" "Should contain env name"
    is "$output" ".*value: 99" "Should contain env value"

    run cat $name.kube
    is "$output" ".*Yaml=$name.yaml" "Should container container port"
    rm $name.kube
    rm $name.yaml
}

# vim: filetype=sh
