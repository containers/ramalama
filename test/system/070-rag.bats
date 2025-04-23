#!/usr/bin/env bats

load helpers

# bats test_tags=distro-integration
@test "ramalama rag" {
    skip_if_nocontainer
    run_ramalama 22 -q rag bogus quay.io/ramalama/myrag:1.2
    is "$output" "Error: bogus does not exist" "Expected failure"

    run_ramalama 22 -q rag README.md quay.io/ramalama/MYRAG:1.2
    is "$output" "Error: invalid reference format: repository name 'quay.io/ramalama/MYRAG:1.2' must be lowercase"

    run_ramalama rag README.md https://github.com/containers/ramalama/blob/main/README.md https://github.com/containers/podman/blob/main/README.md quay.io/ramalama/myrag:1.2

    run_ramalama --dryrun run --rag quay.io/ramalama/myrag:1.2 ollama://smollm:135m
    is "$output" ".*quay.io/ramalama/.*-rag.*" "Expected to use -rag image"
    if not_docker; then
       is "$output" ".*--pull missing.*" "Expected to use --pull missing"
       RAMALAMA_CONFIG=/dev/null run_ramalama --dryrun run --rag quay.io/ramalama/myrag:1.2 ollama://smollm:135m
       is "$output" ".*--pull newer.*" "Expected to use --pull newer"
    fi

    run_ramalama info
    engine=$(echo "$output" | jq --raw-output '.Engine.Name')
    run ${engine} rmi quay.io/ramalama/myrag:1.2
}

# vim: filetype=sh
