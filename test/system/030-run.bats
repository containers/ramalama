#!/usr/bin/env bats

load helpers

MODEL=smollm:135m

@test "ramalama --dryrun run basic output" {
    image=m_$(safename)
    conf=$RAMALAMA_TMPDIR/ramalama.conf
    cat >$conf <<EOF
[ramalama]
pull="missing"
EOF

    if is_container; then
	run_ramalama info
	conman=$(jq .Engine.Name <<< $output | tr -d '"' )
	verify_begin="${conman} run --rm -i --label ai.ramalama --name"

	run_ramalama --dryrun run ${MODEL}
	is "$output" "${verify_begin} ramalama_.*--network none.*" "dryrun correct"
	is "$output" ".*${MODEL}" "verify model name"
	is "$output" ".*-c 2048" "verify model name"
	assert "$output" !~ ".*--seed" "assert seed does not show by default"

	run_ramalama --dryrun run --env a=b --env test=success --name foobar ${MODEL}
	is "$output" "${verify_begin} foobar.*--env a=b --env test=success" "dryrun correct with --env"

	run_ramalama --dryrun run --oci-runtime foobar ${MODEL}
	is "$output" "${verify_begin} .*--runtime foobar" "dryrun correct with --oci-runtime"

	run_ramalama --dryrun run --seed 9876 -c 4096 --net bridge --name foobar ${MODEL}
	is "$output" "${verify_begin} foobar.*--network bridge.*" "dryrun correct with --name"
	is "$output" ".*${MODEL}" "verify model name"
	is "$output" ".*-c 4096" "verify ctx-size is set"
	is "$output" ".*--temp 0.8" "verify temp is set"
	is "$output" ".*--seed 9876" "verify seed is set"
	if not_docker; then
	   is "$output" ".*--pull=newer" "verify pull is newer"
	fi

	run_ramalama --dryrun run --pull=never -c 4096 --name foobar ${MODEL}
	is "$output" ".*--pull=never" "verify pull is never"

	RAMALAMA_CONFIG=${conf} run_ramalama --dryrun run ${MODEL}
	is "$output" ".*--pull=missing" "verify pull is missing"

	run_ramalama 2 --dryrun run --pull=bogus ${MODEL}
	is "$output" ".*error: argument --pull: invalid choice: 'bogus'" "verify pull can not be bogus"

	run_ramalama --dryrun run --name foobar ${MODEL}
	is "$output" "${verify_begin} foobar .*" "dryrun correct with --name"
	assert "$output" =~ ".*--cap-drop=all" "verify --cap-add is present"
	assert "$output" =~ ".*no-new-privileges" "verify --no-new-privs is not present"

	if is_container; then
	    run_ramalama --dryrun run --privileged ${MODEL}
	    is "$output" ".*--privileged" "verify --privileged is set"
	    assert "$output" != ".*--cap-drop=all" "verify --cap-add is not present"
	    assert "$output" != ".*no-new-privileges" "verify --no-new-privs is not present"
	else
	    run_ramalama 1 run --name foobar ${MODEL}
	    is "${lines[0]}"  "Error: --nocontainer and --name options conflict. The --name option requires a container." "conflict between nocontainer and --name line"
	    run_ramalama 1 run --privileged ${MODEL}
	    is "${lines[0]}"  "Error: --nocontainer and --privileged options conflict. The --privileged option requires a container." "conflict between nocontainer and --privileged line"
	fi
	RAMALAMA_IMAGE=${image}:1234 run_ramalama --dryrun run ${MODEL}
	is "$output" ".*${image}:1234 llama-run" "verify image name"

    else
	run_ramalama --dryrun run -c 4096 ${MODEL}
	is "$output" 'llama-run -c 4096 --temp 0.8.*/path/to/model.*' "dryrun correct"
	is "$output" ".*-c 4096" "verify model name"

	run_ramalama 1 run --ctx-size=4096 --name foobar ${MODEL}
	is "${lines[0]}"  "Error: --nocontainer and --name options conflict. The --name option requires a container." "conflict between nocontainer and --name line"
    fi
}

@test "ramalama --dryrun run ensure env vars are respected" {
    skip_if_nocontainer

    ASAHI_VISIBLE_DEVICES=99 run_ramalama --dryrun run ${MODEL}
    is "$output" ".*-e ASAHI_VISIBLE_DEVICES=99" "ensure ASAHI_VISIBLE_DEVICES is set from environment"

    CUDA_LAUNCH_BLOCKING=1 run_ramalama --dryrun run ${MODEL}
    is "$output" ".*-e CUDA_LAUNCH_BLOCKING=1" "ensure CUDA_LAUNCH_BLOCKING is set from environment"

    HIP_VISIBLE_DEVICES=99 run_ramalama --dryrun run ${MODEL}
    is "$output" ".*-e HIP_VISIBLE_DEVICES=99" "ensure HIP_VISIBLE_DEVICES is set from environment"

    HSA_OVERRIDE_GFX_VERSION=0.0.0 run_ramalama --dryrun run ${MODEL}
    is "$output" ".*-e HSA_OVERRIDE_GFX_VERSION=0.0.0" "ensure HSA_OVERRIDE_GFX_VERSION is set from environment"

    HIP_VISIBLE_DEVICES=99 HSA_OVERRIDE_GFX_VERSION=0.0.0 run_ramalama --dryrun run ${MODEL}
    is "$output" ".*-e HIP_VISIBLE_DEVICES=99" "ensure HIP_VISIBLE_DEVICES is set from environment"
    is "$output" ".*-e HSA_OVERRIDE_GFX_VERSION=0.0.0" "ensure HSA_OVERRIDE_GFX_VERSION is set from environment"
}

@test "ramalama run smollm with prompt" {
    run_ramalama run ${MODEL} "What is the first line of the declaration of independence?"
}

@test "ramalama run --keepalive" {
    run_ramalama 124 run --keepalive 1s tiny
}

# vim: filetype=sh
