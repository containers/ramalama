#!/usr/bin/env bats

load helpers

# bats test_tags=distro-integration, ci:parallel
@test "ramalama run - basic tests" {
    rand=$(random_string 30)

    err_no_such_cmd="Error:.*/no/such/command.*[Nn]o such file or directory"
    # vllm: RHEL8 on 2023-07-17: "is a directory".
    # Everything else (llama.cpp; vllm on debian): "permission denied"
    err_no_exec_dir="Error:.*exec.*\\\(permission denied\\\|is a directory\\\)"

    tests="
true              |   0 |
false             |   1 |
sh -c 'exit 32'   |  32 |
echo $rand        |   0 | $rand
/no/such/command  | 127 | $err_no_such_cmd
/etc              | 126 | $err_no_exec_dir
"

    defer-assertion-failures

    tests_run=0
    while read cmd expected_rc expected_output; do
        if [ "$expected_output" = "''" ]; then expected_output=""; fi

        # THIS IS TRICKY: this is what lets us handle a quoted command.
        # Without this incantation (and the "$@" below), the cmd string
        # gets passed on as individual tokens: eg "sh" "-c" "'exit" "32'"
        # (note unmatched opening and closing single-quotes in the last 2).
        # That results in a bizarre and hard-to-understand failure
        # in the BATS 'run' invocation.
        # This should really be done inside parse_table; I can't find
        # a way to do so.
        eval set "$cmd"

        run_ramalama $expected_rc run --rm $IMAGE "$@"
        is "$output" "$expected_output" "ramalama run $cmd - output"

        tests_run=$(expr $tests_run + 1)
    done < <(parse_table "$tests")

    # Make sure we ran the expected number of tests! Until 2019-09-24
    # ramalama-remote was only running one test (the "true" one); all
    # the rest were being silently ignored because of ramalama-remote
    # bug #4095, in which it slurps up stdin.
    is "$tests_run" "$(grep . <<<$tests | wc -l)" "Ran the full set of tests"
}

# bats test_tags=ci:parallel
@test "ramalama run - global runtime option" {
    run_ramalama 126 --runtime-flag invalidflag run --rm $IMAGE
    is "$output" ".*invalidflag" "failed when passing undefined flags to the runtime"
}

# bats test_tags=ci:parallel
@test "ramalama run --memory=0 runtime option" {
    run_ramalama run --memory=0 --rm $IMAGE echo hello
    if is_rootless && ! is_cgroupsv2; then
        is "${lines[0]}" "Resource limits are not supported and ignored on cgroups V1 rootless systems" "--memory is not supported"
        is "${lines[1]}" "hello" "--memory is ignored"
    else
        is "$output" "hello" "failed to run when --memory is set to 0"
    fi
}


# vim: filetype=sh
