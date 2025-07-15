#!/usr/bin/env bats

load helpers

MODEL=smollm:135m

@test "ramalama --dryrun run basic output" {
    image=m_$(safename)
    conf=$RAMALAMA_TMPDIR/ramalama.conf
    cat >$conf <<EOF
[ramalama]
pull="never"
EOF

    if is_container; then
	run_ramalama info
	conman=$(jq -r .Engine.Name <<< $output)
	verify_begin="${conman} run --rm"

	run_ramalama -q --dryrun run ${MODEL}
	is "$output" "${verify_begin}.*"
	is "$output" ".*${MODEL}" "verify model name"
	is "$output" ".*--ctx-size 2048" "verify model name"
	assert "$output" !~ ".*--seed" "assert seed does not show by default"
	assert "$output" !~ ".*-t -i" "assert -t -i not present without tty"

	run_ramalama -q --dryrun run ${MODEL} "what's up doc?"
	is "$output" "${verify_begin}.*"
	assert "$output" !~ ".*-t -i" "run without terminal"

	run_ramalama -q --dryrun run ${MODEL} <<< "Test"
	is "$output" "${verify_begin}.*"
	assert "$output" !~ ".*-t -i" "run without terminal"

	run_ramalama -q --dryrun run --env a=b --env test=success --name foobar ${MODEL}
	is "$output" ".*--env a=b --env test=success" "dryrun correct with --env"

	run_ramalama -q --dryrun run --oci-runtime foobar ${MODEL}
	is "$output" ".*--runtime foobar" "dryrun correct with --oci-runtime"

	RAMALAMA_CONFIG=/dev/null run_ramalama -q --dryrun run --seed 9876 -c 4096 --net bridge --name foobar ${MODEL}
	is "$output" ".*--network bridge.*" "dryrun correct with --name"
	is "$output" ".*${MODEL}" "verify model name"
	is "$output" ".*--ctx-size 4096" "verify ctx-size is set"
	is "$output" ".*--temp 0.8" "verify temp is set"
	is "$output" ".*--seed 9876" "verify seed is set"
	if not_docker; then
	   is "$output" ".*--pull newer" "verify pull is newer"
	fi

	run_ramalama -q --dryrun run ${MODEL}
	is "$output" ".*--pull missing" "verify test defaults"

	run_ramalama -q --dryrun run --pull=never -c 4096 --name foobar ${MODEL}
	is "$output" ".*--pull never" "verify pull is never"

	RAMALAMA_CONFIG=${conf} run_ramalama -q --dryrun run ${MODEL}
	is "$output" ".*--pull never" "verify pull is missing"

	run_ramalama 2 -q --dryrun run --pull=bogus ${MODEL}
	is "$output" ".*error: argument --pull: invalid choice: 'bogus'" "verify pull can not be bogus"

	run_ramalama -q --dryrun run --name foobar ${MODEL}
	is "$output" ".*--name foobar" "dryrun correct with --name"
	is "$output" ".*--cap-drop=all" "verify --cap-add is present"
	is "$output" ".*no-new-privileges" "verify --no-new-privs is not present"
	run_ramalama -q --dryrun run --selinux=True ${MODEL}
	assert "$output" != ".*--security-opt=label=disable" "verify --selinux enables container separation"
	run_ramalama -q --dryrun run --selinux=False ${MODEL}
	assert "$output" =~ ".*--security-opt=label=disable" "verify --selinux=False disbles container separation"
	run_ramalama 22 -q --dryrun run --selinux=100 ${MODEL}
	is "$output" "Error: Cannot coerce '100' to bool" "Should error on bad value"

    run_ramalama -q --dryrun run --runtime-args="--foo -bar" ${MODEL}
    assert "$output" =~ ".*--foo" "--foo passed to runtime"
    assert "$output" =~ ".*-bar" "-bar passed to runtime"

    run_ramalama -q --dryrun run --runtime-args="--foo='a b c'" ${MODEL}
    assert "$output" =~ ".*--foo=a b c" "argument passed to runtime with spaces"

    run_ramalama 22 -q --dryrun run --runtime-args="--foo='a b c" ${MODEL}
    assert "$output" =~ "No closing quotation" "error for improperly quoted runtime arguments"

	if is_container; then
	    run_ramalama -q --dryrun run --privileged ${MODEL}
	    is "$output" ".*--privileged" "verify --privileged is set"
	    assert "$output" != ".*--cap-drop=all" "verify --cap-add is not present"
	    assert "$output" != ".*no-new-privileges" "verify --no-new-privs is not present"
	else
	    run_ramalama 1 run --name foobar ${MODEL}
	    is "${lines[0]}"  "Error: --nocontainer and --name options conflict. The --name option requires a container." "conflict between nocontainer and --name line"
	    run_ramalama 1 run --privileged ${MODEL}
	    is "${lines[0]}"  "Error: --nocontainer and --privileged options conflict. The --privileged option requires a container." "conflict between nocontainer and --privileged line"
	fi
	RAMALAMA_IMAGE=${image}:1234 run_ramalama -q --dryrun run ${MODEL}
	is "$output" ".*${image}:1234.*serve" "verify image name"

    else
	run_ramalama -q --dryrun run --ctx-size 4096 ${MODEL}
	is "$output" '.*serve.*--ctx-size 4096 --temp 0.8.*' "dryrun correct"
	is "$output" ".*--ctx-size 4096" "verify model name"

	run_ramalama 1 run --ctx-size=4096 --name foobar ${MODEL}
	is "${lines[0]}"  "Error: --nocontainer and --name options conflict. The --name option requires a container." "conflict between nocontainer and --name line"
    fi
}

@test "ramalama --dryrun run ensure env vars are respected" {
    skip_if_nocontainer

    ASAHI_VISIBLE_DEVICES=99 run_ramalama -q --dryrun run ${MODEL}
    is "$output" ".*-e ASAHI_VISIBLE_DEVICES=99" "ensure ASAHI_VISIBLE_DEVICES is set from environment"

    CUDA_LAUNCH_BLOCKING=1 run_ramalama -q --dryrun run ${MODEL}
    is "$output" ".*-e CUDA_LAUNCH_BLOCKING=1" "ensure CUDA_LAUNCH_BLOCKING is set from environment"

    HIP_VISIBLE_DEVICES=99 run_ramalama -q --dryrun run ${MODEL}
    is "$output" ".*-e HIP_VISIBLE_DEVICES=99" "ensure HIP_VISIBLE_DEVICES is set from environment"

    HSA_OVERRIDE_GFX_VERSION=0.0.0 run_ramalama -q --dryrun run ${MODEL}
    is "$output" ".*-e HSA_OVERRIDE_GFX_VERSION=0.0.0" "ensure HSA_OVERRIDE_GFX_VERSION is set from environment"

    HIP_VISIBLE_DEVICES=99 HSA_OVERRIDE_GFX_VERSION=0.0.0 run_ramalama -q --dryrun run ${MODEL}
    is "$output" ".*-e HIP_VISIBLE_DEVICES=99" "ensure HIP_VISIBLE_DEVICES is set from environment"
    is "$output" ".*-e HSA_OVERRIDE_GFX_VERSION=0.0.0" "ensure HSA_OVERRIDE_GFX_VERSION is set from environment"
}

@test "ramalama run smollm with prompt" {
    run_ramalama run --temp 0 ${MODEL} "What is the first line of the declaration of independence?"
}

@test "ramalama run --keepalive" {
    # timeout within 1 second and generate a 124 error code.
    run_ramalama 0 --debug run --keepalive 1s tiny
}

@test "ramalama run --image bogus" {
    skip_if_nocontainer
    skip_if_darwin
    skip_if_docker
    run_ramalama 22 run --image bogus --pull=never tiny
    is "$output" ".*Error: bogus: image not known"
    run_ramalama 125 run --image bogus1 --rag quay.io/ramalama/rag --pull=never tiny
    is "$output" ".*Error: bogus1: image not known"
}

@test "ramalama run with rag" {
    skip_if_nocontainer
    skip_if_darwin
    skip_if_docker
    run_ramalama --dryrun run --rag quay.io/ramalama/rag --pull=never tiny
    is "$output" ".*quay.io/ramalama/.*-rag:"

    run_ramalama --dryrun run --image quay.io/ramalama/ramalama:1.0 --rag quay.io/ramalama/rag --pull=never tiny
    is "$output" ".*quay.io/ramalama/ramalama:1.0"
}

# vim: filetype=sh
