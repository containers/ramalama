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
	is "$output" ".*-c 2048" "verify model name"
	assert "$output" !~ ".*--seed" "assert seed does not show by default"

	run_ramalama --dryrun run --seed 9876 -c 4096 --name foobar ${model}
	is "$output" "${verify_begin} foobar .*" "dryrun correct with --name"
	is "$output" ".*${model}" "verify model name"
	is "$output" ".*-c 4096" "verify ctx-size is set"
	is "$output" ".*--temp 0.8" "verify temp is set"
	is "$output" ".*--seed 9876" "verify seed is set"

	run_ramalama --dryrun run --name foobar ${model}
	is "$output" "${verify_begin} foobar .*" "dryrun correct with --name"

	run_ramalama 1 --nocontainer run --name foobar tiny
	is "${lines[0]}"  "Error: --nocontainer and --name options conflict. --name requires a container." "conflict between nocontainer and --name line"

	RAMALAMA_IMAGE=${image} run_ramalama --dryrun run ${model}
	is "$output" ".*${image} /bin/sh -c" "verify image name"
    else
	run_ramalama --dryrun run -c 4096 ${model}
	is "$output" 'llama-cli -m /path/to/model --in-prefix --in-suffix -c 4096 --temp 0.8 --no-display-prompt -p.*' "dryrun correct"
	is "$output" ".*-c 4096" "verify model name"

	run_ramalama 1 run --ctx-size=4096 --name foobar tiny
	is "${lines[0]}"  "Error: --nocontainer and --name options conflict. --name requires a container." "conflict between nocontainer and --name line"
    fi
}

@test "ramalama run tiny with prompt" {
      skip_if_notlocal
      run_ramalama run --name foobar tiny "Write a 1 line poem"
}

# vim: filetype=sh
