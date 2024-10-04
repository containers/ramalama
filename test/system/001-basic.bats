#!/usr/bin/env bats
#
# Simplest set of ramalama tests. If any of these fail, we have serious problems.
#

load helpers

# Override standard setup! We don't yet trust ramalama-images or ramalama-rm
function setup() {
    # Makes test logs easier to read
    BATS_TEST_NAME_PREFIX="[001] "
}

#### DO NOT ADD ANY TESTS HERE! ADD NEW TESTS AT BOTTOM!

# bats test_tags=distro-integration
@test "ramalama version" {
    run_ramalama version
    is "$output" "ramalama version .*"               "'Version line' in output with version command"

    run_ramalama -v
    is "$output" "ramalama version .*"               "'Version line' in output with -v "
}

# vim: filetype=sh
