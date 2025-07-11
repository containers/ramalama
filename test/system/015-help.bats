#!/usr/bin/env bats
#
# Tests based on 'ramalama help'
#
# Find all commands listed by 'ramalama --help'. Run each one, make sure it
# provides its own --help output.
# Any usage message that ends in '[options]' is interpreted as a command
# that takes no further arguments; we confirm by running with 'invalid-arg'
# and confirming that it exits with error status and message.
#
load helpers

function check_help() {
    local count=0
    local found

    echo $(_ramalama_commands "$@")
    for cmd in $(_ramalama_commands "$@"); do
        # Human-readable ramalama command string, with multiple spaces collapsed
        command_string="ramalama $* $cmd"
        command_string=${command_string//  / }  # 'ramalama  x' -> 'ramalama x'

        dprint "$command_string --help"
        run_ramalama "$@" $cmd --help
        local full_help="$output"

        # The line immediately after 'usage:' gives us a 1-line synopsis
         usage=$(echo "$full_help" | grep -A4 '^usage:')
        assert "$usage" != "" "ramalama $cmd: no usage message found"

        # Strip off the leading command string; we no longer need it
        usage=$(sed -e "s/^  $command_string \?//" <<<"$usage")

        # If usage ends in '[command]', recurse into subcommands
        if expr "$usage" : '\[command\]' >/dev/null; then
            found[subcommands]=1
            # (except for 'ramalama help', which is a special case)
            if [[ $cmd != "help" ]]; then
                check_help "$@" $cmd
            fi
            continue
        fi

        # Cross-check: if usage includes '[options]', there must be a
        # longer 'options:' section in the full --help output; vice-versa,
        # if 'options:' is in full output, usage line must have '[options]'.
	if ! expr "$full_help" : ".*options:" >/dev/null; then
           die "$command_string: usage includes '[options]' but has no 'Options:' subsection"
        fi
        # If usage lists no arguments (strings in ALL CAPS), confirm
        # by running with 'invalid-arg' and expecting failure.
        if ! expr "$usage" : '.*[A-Z]' >/dev/null; then
            if [ "$cmd" != "help" ]; then
                dprint "$command_string invalid-arg"
                run_ramalama '?' "$@" $cmd invalid-arg
                is "$status" 2 \
                   "'$usage' indicates that the command takes no arguments. I invoked it with 'invalid-arg' and expected an error status"
                is "$output" ".*ramalama: error: unrecognized arguments: invalid-arg" \
                   "'$usage' indicates that the command takes no arguments. I invoked it with 'invalid-arg' and expected the following error message"
            fi
            found[takes_no_args]=1
        fi

        # If usage has required arguments, try running without them.
        if expr "$usage" : '[A-Z]' >/dev/null; then
            # The </dev/null protects us from 'ramalama login' which will
            # try to read username/password from stdin.
            dprint "$command_string (without required args)"
            run_ramalama '?' "$@" $cmd </dev/null
            is "$status" 2 \
               "'$usage' indicates at least one required arg. I invoked it with no args and expected an error exit code"
            is "$output" "Error:.* \(require\|must\|provide\|need\|choose\|accepts\)" \
               "'$usage' indicates at least one required arg. I invoked it with no args and expected one of these error messages"

            found[required_args]=1
        fi

        count=$(expr $count + 1)
    done

    # Any command that takes subcommands, prints its help and errors if called
    # without one.
    dprint "ramalama $*"
    run_ramalama "$@"

    # Assume that 'NoSuchCommand' is not a command
    dprint "ramalama $* NoSuchCommand"
    run_ramalama '?' "$@" NoSuchCommand
    is "$status" 2 "'ramalama $* NoSuchCommand' - exit status"
    is "$output" ".*ramalama: error: argument subcommand: invalid choice: .*'NoSuchCommand'" \
       "'ramalama $* NoSuchCommand' - expected error message"
}


@test "ramalama help - basic tests" {

    # Called with no args -- start with 'ramalama --help'. check_help() will
    # recurse for any subcommands.
    check_help

    # Test for regression of #7273 (spurious "--remote" help on output)
    for helpopt in help --help -h; do
        run_ramalama $helpopt
        is "${lines[0]}" "usage: ramalama [-h] [--debug] [--dryrun] [--engine ENGINE] [--nocontainer]" \
           "ramalama $helpopt: first line of output"
    done

}

@test "ramalama verify default image" {

    unset RAMALAMA_IMAGE
    run_ramalama run --help
    is "$output" ".*image IMAGE.*OCI container image to run with the specified AI model"  "Verify default image"
    is "$output" ".*default: quay.io/ramalama/.*"  "Verify default image"

    image=m_$(safename)
    RAMALAMA_IMAGE=${image} run_ramalama run --help
    is "$output" ".*default: ${image}"  "Verify default image from environment"

    conf=$RAMALAMA_TMPDIR/ramalama.conf
    cat >$conf <<EOF
[ramalama]
image="$image"
EOF

    RAMALAMA_CONFIG=${conf} run_ramalama bench --help
    is "$output" ".*default: ${image}"  "Verify default image from ramalama.conf"

    image1=m_$(safename)
    RAMALAMA_IMAGE=${image1} RAMALAMA_CONFIG=${conf} run_ramalama serve --help
    is "$output" ".*default: ${image1}"  "Verify default image from environment over ramalama.conf"
}

@test "ramalama verify default engine" {
    engine=e_$(safename)
    RAMALAMA_CONTAINER_ENGINE=${engine} run_ramalama --help
    is "$output" ".*default: ${engine}"  "Verify default engine from environment variable"

    conf=$RAMALAMA_TMPDIR/ramalama.conf
    cat >$conf <<EOF
[ramalama]
engine="$engine"
EOF

    RAMALAMA_CONFIG=${conf} run_ramalama --help
    is "$output" ".*default: ${engine}"  "Verify default engine from ramalama.conf"

    engine1=e_$(safename)
    RAMALAMA_CONTAINER_ENGINE=${engine1} RAMALAMA_CONFIG=${conf} run_ramalama --help
    is "$output" ".*default: ${engine1}"  "Verify default engine from environment variable override ramamalama.conf"

    engine2=e_$(safename)
    RAMALAMA_CONTAINER_ENGINE=${engine1} RAMALAMA_CONFIG=${conf} run_ramalama --engine ${engine2} --help
    is "$output" ".*default: ${engine2}"  "Verify --engine rules them all"
}

@test "ramalama verify default runtime" {
    run_ramalama --help
    is "$output" ".*default: llama.cpp"  "Verify default runtime from environment variable"

    conf=$RAMALAMA_TMPDIR/ramalama.conf
    cat >$conf <<EOF
[ramalama]
runtime="vllm"
EOF

    RAMALAMA_CONFIG=${conf} run_ramalama --help
    is "$output" ".*default: vllm"  "Verify default runtime from ramalama.conf"
}

@test "ramalama verify default store" {
    store=e_$(safename)
    run_ramalama --help
    if is_rootless; then
        is "$output" ".*default: ${HOME}/.local/share/ramalama"  "Verify default store"
    else
        is "$output" ".*default: /var/lib/ramalama"  "Verify default store"
    fi

    conf=$RAMALAMA_TMPDIR/ramalama.conf
    cat >$conf <<EOF
[ramalama]
store="$store"
EOF

    RAMALAMA_CONFIG=${conf} run_ramalama --help
    is "$output" ".*default: ${store}"  "Verify default store from ramalama.conf"

    store1=e_$(safename)
    RAMALAMA_CONFIG=${conf} run_ramalama --store=${store1} --help
    is "$output" ".*default: ${store1}"  "Verify default store from ramalama.conf"
}

@test "ramalama verify default container" {
    skip_if_nocontainer

    run_ramalama --help
    is "$output" ".*The RAMALAMA_IN_CONTAINER environment variable modifies default behaviour. (default: False)"  "Verify default container"

    RAMALAMA_IN_CONTAINER=false run_ramalama --help
    is "$output" ".*The RAMALAMA_IN_CONTAINER environment variable modifies default behaviour. (default: True)"  "Verify default container with environment"

    conf=$RAMALAMA_TMPDIR/ramalama.conf
    cat >$conf <<EOF
[ramalama]
container=false
EOF

    RAMALAMA_CONFIG=${conf} run_ramalama --help
    is "$output" ".*The RAMALAMA_IN_CONTAINER environment variable modifies default behaviour. (default: True)"  "Verify default container override in ramalama.conf"
}

@test "ramalama verify transport" {
    transport=e_$(safename)
    RAMALAMA_TRANSPORT=${transport} run_ramalama 1 pull foobar
    is "$output" "Error: transport \"${transport}\" not supported. Must be oci, huggingface, modelscope, or ollama."  "Verify bogus transport throws error"

}

@test "ramalama verify default port" {

    run_ramalama serve --help
    is "$output" ".*port for AI Model server to listen on.*8080"  "Verify default port"

    conf=$RAMALAMA_TMPDIR/ramalama.conf
    cat >$conf <<EOF
[ramalama]
port="1776"
EOF

    RAMALAMA_CONFIG=${conf} run_ramalama serve --help
    is "$output" ".*port for AI Model server to listen on.*1776"  "Verify default port"
}

@test "ramalama verify one argument to rm" {

    run_ramalama 22 rm
    is "$output" "Error: one MODEL or --all must be specified"  "Verify at least one argument"
}

# vim: filetype=sh
