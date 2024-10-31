#!/usr/bin/env bats

load helpers

@test "ramalama --dryrun run basic output" {
    skip_if_nocontainer

    model=tiny
    image=m_$(safename)

    run_ramalama info
    conman=$(jq .Engine <<< $output | tr -d '"' )
    verify_begin="${conman} run --rm -i --label RAMALAMA --security-opt=label=disable --name"

    run_ramalama --dryrun run ${model}
    is "$output" "${verify_begin} ramalama_.*" "dryrun correct"
    is "$output" ".*${model}" "verify model name"

    run_ramalama --dryrun run --name foobar ${model}
    is "$output" "${verify_begin} foobar .*" "dryrun correct with --name"
    is "$output" ".*${model}" "verify model name"

    run_ramalama --dryrun run --name foobar ${model}
    is "$output" "${verify_begin} foobar .*" "dryrun correct with --name"

    run_ramalama 1 --nocontainer run --name foobar tiny
    is "${lines[0]}"  "Error: --nocontainer and --name options conflict. --name requires a container." "conflict between nocontainer and --name line"

    RAMALAMA_IMAGE=${image} run_ramalama --dryrun run ${model}
    is "$output" ".*${image} llama-cli -m" "verify image name"
}

# FIXME no way to run this reliably without flakes in CI/CD system
#@test "ramalama run granite with prompt" {
#    run_ramalama run --name foobar granite "How often to full moons happen"
#    is "$output" ".*month" "should include some info about the Moon"
#    run_ramalama list
#    is "$output" ".*granite" "granite model should have been pulled"
#}

# vim: filetype=sh
