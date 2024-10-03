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
    local -A found

    echo $(_ramalama_commands "$@")
    for cmd in $(_ramalama_commands "$@"); do
        # Human-readable ramalama command string, with multiple spaces collapsed
        command_string="ramalama $* $cmd"
        command_string=${command_string//  / }  # 'ramalama  x' -> 'ramalama x'

        dprint "$command_string --help"
        run_ramalama "$@" $cmd --help
        local full_help="$output"

        # The line immediately after 'usage:' gives us a 1-line synopsis
        usage=$(echo "$full_help" | grep -A1 '^usage:')
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

        # If command lists "-l, --latest" in help output, combine -l with arg.
        # This should be disallowed with a clear message.
        if expr "$full_help" : ".*-l, --latest" >/dev/null; then
            local nope="exec list port ps top"   # these can't be tested
            if ! grep -wq "$cmd" <<<$nope; then
                run_ramalama 2 "$@" $cmd -l nonexistent-container
                is "$output" "Error: .*--latest and \(containers\|pods\|arguments\) cannot be used together" \
                   "'$command_string' with both -l and container"

                # Combine -l and -a, too (but spell it as --all, because "-a"
                # means "attach" in ramalama container start)
                run_ramalama 2 "$@" $cmd --all --latest
                is "$output" "Error: \(--all and --latest cannot be used together\|--all, --latest and containers cannot be used together\|--all, --latest and arguments cannot be used together\|unknown flag\)" \
                   "'$command_string' with both --all and --latest"
            fi
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

        # Commands with fixed number of arguments (i.e. no ellipsis): count
        # the required args, then invoke with one extra. We should get a
        # usage error.
        if ! expr "$usage" : ".*\.\.\."; then
            local n_args=$(wc -w <<<"$usage")

            run_ramalama '?' "$@" $cmd $(seq --format='x%g' 0 $n_args)
            is "$status" 2 \
               "'$usage' indicates a maximum of $n_args args. I invoked it with more, and expected this exit status"
            is "$output" ".*ramalama: error:.* unrecognized arguments" \
               "'$usage' indicates a maximum of $n_args args. I invoked it with more, and expected one of these error messages"

            found[fixed_args]=1
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
        is "${lines[0]}" "usage: ramalama [-h] [--store STORE] [--dryrun] [--container] [--nocontainer]" \
           "ramalama $helpopt: first line of output"
    done

}

# vim: filetype=sh
