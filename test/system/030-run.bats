#!/usr/bin/env bats

load helpers

@test "ramalama --dryrun run basic output" {
    model=tiny
    image=m_$(safename)

    if is_container; then
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
	is "$output" ".*${image} /bin/sh -c" "verify image name"
    else
	run_ramalama --dryrun run ${model}
	is "$output" 'llama-cli -m /path/to/model --in-prefix --in-suffix --no-display-prompt -p.*' "dryrun correct"

	run_ramalama 1 run --name foobar tiny
	is "${lines[0]}"  "Error: --nocontainer and --name options conflict. --name requires a container." "conflict between nocontainer and --name line"
    fi
}

@test "ramalama run tiny with prompt" {
      skip_if_notlocal
      run_ramalama run --name foobar tiny "Write a 1 line poem"
}

# vim: filetype=sh
