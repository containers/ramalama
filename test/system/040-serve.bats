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
    is "$output" "${verify_begin} ramalama_.*" "run in detach mode"

    run_ramalama --dryrun serve -d ${model}
    is "$output" "${verify_begin} ramalama_.*" "dryrun correct"
}

@test "ramalama --detach serve and stop" {
    model=ollama://tiny-llm:latest 
    container=c_$(safename)

    run_ramalama serve --name ${container} --detach ${model}
    
    run_ramalama ps 
    run_ramalama containers --noheading
    is "$output" ".*${container}" "dryrun correct"

    run_ramalama stop ${container}
}

# vim: filetype=sh
