# -*- bash -*-

# RamaLama command to run; 
RAMALAMA=${RAMALAMA:-ramalama}

export RAMALAMA_CONFIG=${RAMALAMA_CONFIG:-./test/system/ramalama.conf}

# llama.cpp or vllm, unlikely to change. Cache, because it's expensive to determine.
RAMALAMA_RUNTIME=

# Standard image to use for most tests
RAMALAMA_TEST_IMAGE_REGISTRY=${RAMALAMA_TEST_IMAGE_REGISTRY:-"quay.io"}
RAMALAMA_TEST_IMAGE_USER=${RAMALAMA_TEST_IMAGE_USER:-"libpod"}
RAMALAMA_TEST_IMAGE_NAME=${RAMALAMA_TEST_IMAGE_NAME:-"testimage"}
RAMALAMA_TEST_IMAGE_TAG=${RAMALAMA_TEST_IMAGE_TAG:-"20240123"}
RAMALAMA_TEST_IMAGE_FQN="$RAMALAMA_TEST_IMAGE_REGISTRY/$RAMALAMA_TEST_IMAGE_USER/$RAMALAMA_TEST_IMAGE_NAME:$RAMALAMA_TEST_IMAGE_TAG"

# Remote image that we *DO NOT* fetch or keep by default; used for testing pull
# This has changed in 2021, from 0 through 3, various iterations of getting
# multiarch to work. It should change only very rarely.
RAMALAMA_NONLOCAL_IMAGE_TAG=${RAMALAMA_NONLOCAL_IMAGE_TAG:-"00000004"}
RAMALAMA_NONLOCAL_IMAGE_FQN="$RAMALAMA_TEST_IMAGE_REGISTRY/$RAMALAMA_TEST_IMAGE_USER/$RAMALAMA_TEST_IMAGE_NAME:$RAMALAMA_NONLOCAL_IMAGE_TAG"

# Because who wants to spell that out each time?
IMAGE=$RAMALAMA_TEST_IMAGE_FQN

MODEL=ollama://smollm:135m

load helpers.podman

# Default timeout for a ramalama command.
RAMALAMA_TIMEOUT=${RAMALAMA_TIMEOUT:-600}

# Prompt to display when logging ramalama commands; distinguish root/rootless
_LOG_PROMPT='$'
if [ $(id -u) -eq 0 ]; then
    _LOG_PROMPT='#'
fi

###############################################################################
# BEGIN tools for fetching & caching test images
#
# Registries are flaky: any time we have to pull an image, that's a risk.
#

# Store in a semipermanent location. Not important for CI, but nice for
# developers so test restarts don't hang fetching images.
export RAMALAMA_IMAGECACHE=${BATS_TMPDIR:-/tmp}/ramalama-systest-imagecache-$(id -u)
mkdir -p ${RAMALAMA_IMAGECACHE}

###############################################################################
# BEGIN setup/teardown tools

# Provide common setup and teardown functions, but do not name them such!
# That way individual tests can override with their own setup/teardown,
# while retaining the ability to include these if they so desire.

# Setup helper: establish a test environment with exactly the images needed
function ramalama_basic_setup() {
    # Temporary subdirectory, in which tests can write whatever they like
    # and trust that it'll be deleted on cleanup.
    # (BATS v1.3 and above provide $BATS_TEST_TMPDIR, but we still use
    # ancient BATS (v1.1) in RHEL gating tests.)
    RAMALAMA_TMPDIR=$(mktemp -d --tmpdir=${BATS_TMPDIR:-/tmp} ramalama_bats.XXXXXX)

    # runtime is not likely to change
    if [[ -z "$RAMALAMA_RUNTIME" ]]; then
        RAMALAMA_RUNTIME=$(ramalama_runtime)
    fi

    # In the unlikely event that a test runs is() before a run_ramalama()
    MOST_RECENT_RAMALAMA_COMMAND=

    # Test filenames must match ###-name.bats; use "[###] " as prefix
    run expr "$BATS_TEST_FILENAME" : "^.*/\([0-9]\{3\}\)-[^/]\+\.bats\$"
    BATS_TEST_NAME_PREFIX="[${output}] "

    # By default, assert() and die() cause an immediate test failure.
    # Under special circumstances (usually long test loops), tests
    # can call defer-assertion-failures() to continue going, the
    # idea being that a large number of failures can show patterns.
    ASSERTION_FAILURES=
    immediate-assertion-failures
}

# Provide the above as default methods.
function setup() {
    ramalama_basic_setup
}

# END   setup/teardown tools
###############################################################################
# BEGIN ramalama helpers

################
#  run_ramalama  #  Invoke $RAMALAMA, with timeout, using BATS 'run'
################
#
# This is the preferred mechanism for invoking ramalama: first, it
# invokes $RAMALAMA or '/some/path/ramalama'.
#
# Second, we use 'timeout' to abort (with a diagnostic) if something
# takes too long; this is preferable to a CI hang.
#
# Third, we log the command run and its output. This doesn't normally
# appear in BATS output, but it will if there's an error.
#
# Next, we check exit status. Since the normal desired code is 0,
# that's the default; but the first argument can override:
#
#     run_ramalama 125  nonexistent-subcommand
#     run_ramalama '?'  some-other-command       # let our caller check status
#
# Since we use the BATS 'run' mechanism, $output and $status will be
# defined for our caller.
#
function run_ramalama() {
    # Number as first argument = expected exit code; default 0
    # "0+[we]" = require success, but allow warnings/errors
    local expected_rc=0
    local allowed_levels="dit"
    case "$1" in
        0\+[we]*)        allowed_levels+=$(expr "$1" : "^0+\([we]\+\)"); shift;;
        [0-9])           expected_rc=$1; shift;;
        [1-9][0-9])      expected_rc=$1; shift;;
        [12][0-9][0-9])  expected_rc=$1; shift;;
        '?')             expected_rc=  ; shift;;  # ignore exit code
    esac

    # Remember command args, for possible use in later diagnostic messages
    MOST_RECENT_RAMALAMA_COMMAND="ramalama $*"

    # BATS >= 1.5.0 treats 127 as a special case, adding a big nasty warning
    # at the end of the test run if any command exits thus. Silence it.
    #   https://bats-core.readthedocs.io/en/stable/warnings/BW01.html
    local silence127=
    if [[ "$expected_rc" = "127" ]]; then
        # We could use "-127", but that would cause BATS to fail if the
        # command exits any other status -- and default BATS failure messages
        # are much less helpful than the run_ramalama ones. "!" is more flexible.
        silence127="!"
    fi

    # stdout is only emitted upon error; this printf is to help in debugging
    printf "\n%s %s %s %s\n" "$(timestamp)" "$_LOG_PROMPT" "$RAMALAMA" "$*"
    # BATS hangs if a subprocess remains and keeps FD 3 open; this happens
    # if ramalama crashes unexpectedly without cleaning up subprocesses.
    run $silence127 timeout --foreground -v --kill=10 $RAMALAMA_TIMEOUT $RAMALAMA $_RAMALAMA_TEST_OPTS "$@" 3>/dev/null
    # without "quotes", multiple lines are glommed together into one
    if [ -n "$output" ]; then
        echo "$(timestamp) $output"

        # FIXME FIXME FIXME: instrumenting to track down #15488. Please
        # remove once that's fixed. We include the args because, remember,
        # bats only shows output on error; it's possible that the first
        # instance of the metacopy warning happens in a test that doesn't
        # check output, hence doesn't fail.
        if [[ "$output" =~ Ignoring.global.metacopy.option ]]; then
            echo "# YO! metacopy warning triggered by: ramalama $*" >&3
        fi
    fi
    if [ "$status" -ne 0 ]; then
        echo -n "$(timestamp) [ rc=$status ";
        if [ -n "$expected_rc" ]; then
            if [ "$status" -eq "$expected_rc" ]; then
                echo -n "(expected) ";
            else
                echo -n "(** EXPECTED $expected_rc **) ";
            fi
        fi
        echo "]"
    fi

    if [ "$status" -eq 124 ]; then
        if expr "$output" : ".*timeout: sending" >/dev/null; then
            # It's possible for a subtest to _want_ a timeout
            if [[ "$expected_rc" != "124" ]]; then
                echo "*** TIMED OUT ***"
                false
            fi
        fi
    fi

    if [ -n "$expected_rc" ]; then
        if [ "$status" -ne "$expected_rc" ]; then
            die "exit code is $status; expected $expected_rc"
        fi
    fi
}

function run_ramalama_testing() {
    printf "\n%s %s %s %s\n" "$(timestamp)" "$_LOG_PROMPT" "$RAMALAMA_TESTING" "$*"
    run $RAMALAMA_TESTING "$@"
    if [[ $status -ne 0 ]]; then
        echo "$output"
        die "Unexpected error from testing helper, which should always always succeed"
    fi
}

# END   ramalama helpers
###############################################################################
# BEGIN miscellaneous tools

# Returns the OCI runtime *basename* (typically llama.cpp or vllm). Much as we'd
# love to cache this result, we probably shouldn't.
function ramalama_runtime() {
    # This function is intended to be used as '$(ramalama_runtime)', i.e.
    # our caller wants our output. It's unsafe to use run_ramalama().
    runtime=$($RAMALAMA $_RAMALAMA_TEST_OPTS info | jq -r .Runtime 2>/dev/null)
    basename "${runtime:-[null]}"
}

# return that list.
function _ramalama_commands() {
    dprint "$@"
    # &>/dev/null prevents duplicate output
    run_ramalama help "$@" &>/dev/null
    awk '/^positional arguments:/{ok=1;next;}/^options:/{ok=0}ok { print $1 }' <<<"$output" | grep -v help | grep .
}

function is_container() {
    [ "${_RAMALAMA_TEST_OPTS}" != "--nocontainer" ]
}

function not_docker() {
    [[ "${_RAMALAMA_TEST_OPTS}" != "--engine=docker" ]]
}

function skip_if_nocontainer() {
    if [[ "${_RAMALAMA_TEST_OPTS}" == "--nocontainer" ]]; then
	skip "Not supported with --nocontainer"
    fi
}

function skip_if_notlocal() {
    if [[ "${_RAMALAMA_TEST}" != "local" ]]; then
	skip "Not supported unless --local"
    fi
}

function skip_if_docker() {
    if [[ "${_RAMALAMA_TEST_OPTS}" == "--engine=docker" ]]; then
	skip "Not supported with ----engine=docker"
    fi
}

function is_darwin() {
    [ "$(uname)" == "Darwin" ]
}

function is_tty() {
    tty -s
}

function skip_if_darwin() {
    if [[ "$(uname)" == "Darwin" ]]; then
	skip "Not supported on darwin"
    fi
}

function is_apple_silicon() {
    # Check if we're on macOS and have Apple Silicon (arm64)
    if is_darwin; then
        arch=$(uname -m)
        [[ "$arch" == "arm64" ]]
    else
        return 1
    fi
}

function skip_if_no_hf-cli(){
    if ! command -v huggingface-cli 2>&1 >/dev/null
    then
        skip "Not supported without huggingface-cli"
    fi
}

function skip_if_no_ollama() {
    if ! command -v ollama 2>&1 >/dev/null
    then
        skip "Not supported without ollama"
    fi
}

# END   miscellaneous tools
###############################################################################
