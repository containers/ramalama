#!/usr/bin/env bats

load helpers

# bats test_tags=distro-integration
@test "ramalama info" {
    #FIXME jq version on mac does not like regex handling
    skip_if_darwin
    run_ramalama 2 info bogus
    is "$output" ".*ramalama: error: unrecognized arguments: bogus"

    run_ramalama -v
    version=$(cut -f3 -d " " <<<"$output")

    run_ramalama info

    # FIXME Engine  (podman|docker|'')
    tests="
Image   | "quay.io/ramalama/ramalama:latest"
Runtime | "llama-cpp-python"
Version | "${version}"
Store   | \\\("${HOME}/.local/share/ramalama"\\\|"/var/lib/ramalama"\\\)
"

    defer-assertion-failures

    while read field expect; do
        actual=$(echo "$output" | jq -r ".$field")
        dprint "# actual=<$actual> expect=<$expect>"
        is "$actual" "$expect" "jq .$field"
    done < <(parse_table "$tests")

    image=i_$(safename)
    runtime=vllm
    engine=e_$(safename)
    store=s_$(safename)

    run_ramalama --store $store --runtime $runtime --engine $engine --image $image info
    tests="
Engine  | $engine
Image   | $image
Runtime | $runtime
Store   | $store
"

    defer-assertion-failures

    while read field expect; do
        actual=$(echo "$output" | jq -r ".$field")
        dprint "# actual=<$actual> expect=<$expect>"
        is "$actual" "$expect" "jq .$field"
    done < <(parse_table "$tests")

}

# vim: filetype=sh
