#!/usr/bin/env bats

load helpers

@test "ramalama --dryrun run basic output" {
    model=m_$(safename)

    verify_begin="podman run --rm -it --label \"RAMALAMA container\" --security-opt=label=disable -v/tmp:/tmp -e RAMALAMA_TRANSPORT --name"

    run_ramalama --dryrun run ${model}
    is "$output" "${verify_begin} ramalama_.*" "dryrun correct"
    is "$output" ".*${model}" "verify model name"

    run_ramalama --dryrun run --name foobar ${model}
    is "$output" "${verify_begin} foobar .*" "dryrun correct with --name"
    is "$output" ".*${model}" "verify model name"

    run_ramalama --dryrun run --name foobar MODEL
    is "$output" "${verify_begin} foobar .*" "dryrun correct with --name"

    run_ramalama 22 --nocontainer run --name foobar MODEL
    is "${lines[0]}"  "--nocontainer and --name options conflict. --name requires a container." "conflict between nocontainer and --name line"
}

@test "ramalama run granite with prompt" {
    run_ramalama run --name foobar granite "How often to full moons happen"
    is "$output" ".*Moon" "should include some info about the Moon"
    run_ramalama list
    is "$output" ".*granite" "granite model should have been pulled"
}

# vim: filetype=sh
