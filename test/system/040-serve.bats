#!/usr/bin/env bats

load helpers

verify_begin="podman run --rm -it --label=RAMALAMA container --security-opt=label=disable -v/tmp:/tmp -e RAMALAMA_TRANSPORT --name"

@test "ramalama --dryrun serve basic output" {
    model=m_$(safename)

    run_ramalama --dryrun serve ${model}
    is "$output" "${verify_begin} ramalama_.*" "dryrun correct"
    is "$output" ".*${model}" "verify model name"

    run_ramalama --dryrun serve --name foobar ${model}
    is "$output" "${verify_begin} foobar .*" "dryrun correct with --name"
    is "$output" ".*${model}" "verify model name"

    run_ramalama --dryrun serve --name foobar MODEL
    is "$output" "${verify_begin} foobar .*" "dryrun correct with --name"

    run_ramalama 22 --nocontainer serve --name foobar MODEL
    is "${lines[0]}"  "--nocontainer and --name options conflict. --name requires a container." "conflict between nocontainer and --name line"
}

@test "ramalama --detach serve" {
    model=m_$(safename)

    run_ramalama --dryrun serve --detach ${model}
    is "$output" "${verify_begin} ramalama_.*" "serve in detach mode"

    run_ramalama --dryrun serve -d ${model}
    is "$output" "${verify_begin} ramalama_.*" "dryrun correct"
}

@test "ramalama serve and stop" {
    model=ollama://tiny-llm:latest
    container=c_$(safename)

    run_ramalama serve --name ${container} --detach ${model}; echo READY
    cid="$output"
    wait_for_ready $cid
    run_ramalama ps
    is "$output" ".*${container}" "list correct"
    run_ramalama containers --noheading
    is "$output" ".*${container}" "list correct"
    run_ramalama stop ${container}

    run_ramalama serve -d ${model}; echo READY
    cid="$output"
    wait_for_ready $cid
    run_ramalama containers
    is "$output" ".*${cid}" "list correct with cid"
    run_ramalama ps --noheading
    is "$output" ".*${container}" "list correct with cid and no heading"
    run_ramalama stop ${cid}
}

@test "ramalama --detach serve and stop all" {
    model=ollama://tiny-llm:latest
    container=c_$(safename)

    run_ramalama stop --all

    run_ramalama serve --detach ${model}; echo READY
    cid="$output"
    wait_for_ready $cid

    run_ramalama serve -p 8081 --detach ${model}; echo READY
    cid="$output"
    wait_for_ready $cid

    run_ramalama containers --noheading
    is ${#lines[@]} 2 "two containers should be running"

    run_ramalama stop --all
    run_ramalama containers -n
    is "$output" "" "no more containers should exist"
}

# vim: filetype=sh
