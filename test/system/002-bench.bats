#!/usr/bin/env bats
#
# Simplest set of ramalama tests. If any of these fail, we have serious problems.
#

load helpers

# Override standard setup! We don't yet trust ramalama-images or ramalama-rm
function setup() {
    # Makes test logs easier to read
    BATS_TEST_NAME_PREFIX="[002] "
}

#### DO NOT ADD ANY TESTS HERE! ADD NEW TESTS AT BOTTOM!

# bats test_tags=distro-integration
@test "ramalama bench" {
    skip_if_nocontainer
    run_ramalama bench -t 2 $(test_model smollm:135m)
    is "$output" ".*model.*size.*" "model and size in output"
}

# vim: filetype=sh
