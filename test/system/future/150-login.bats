#!/usr/bin/env bats   -*- bats -*-
#
# tests for ramalama login
#

load helpers
load helpers.registry

###############################################################################
# BEGIN filtering - none of these tests will work with ramalama-remote

function setup() {
    basic_setup
    start_registry
}

# END   filtering - none of these tests will work with ramalama-remote
###############################################################################
# BEGIN actual tests
# BEGIN primary ramalama login/push/pull tests

@test "ramalama login - basic test" {
    run_ramalama login --tls-verify=false \
               --username ${RAMALAMA_LOGIN_USER} \
               --password-stdin \
               localhost:${RAMALAMA_LOGIN_REGISTRY_PORT} <<<"${RAMALAMA_LOGIN_PASS}"
    is "$output" "Login Succeeded!" "output from ramalama login"

    # Now log out
    run_ramalama logout localhost:${RAMALAMA_LOGIN_REGISTRY_PORT}
    is "$output" "Removed login credentials for localhost:${RAMALAMA_LOGIN_REGISTRY_PORT}" \
       "output from ramalama logout"
}

@test "ramalama login - with wrong credentials" {
    registry=localhost:${RAMALAMA_LOGIN_REGISTRY_PORT}

    run_ramalama 125 login --tls-verify=false \
               --username ${RAMALAMA_LOGIN_USER} \
               --password-stdin \
               $registry <<< "x${RAMALAMA_LOGIN_PASS}"
    is "$output" \
       "Error: logging into \"$registry\": invalid username/password" \
       'output from ramalama login'
}

@test "ramalama login - check generated authfile" {
    authfile=${RAMALAMA_LOGIN_WORKDIR}/auth-$(random_string 10).json
    rm -f $authfile

    registry=localhost:${RAMALAMA_LOGIN_REGISTRY_PORT}

    run_ramalama login --authfile=$authfile \
        --tls-verify=false \
        --username ${RAMALAMA_LOGIN_USER} \
        --password ${RAMALAMA_LOGIN_PASS} \
        $registry

    # Confirm that authfile now exists
    test -e $authfile || \
        die "ramalama login did not create authfile $authfile"

    # Special bracket form needed because of colon in host:port
    run jq -r ".[\"auths\"][\"$registry\"][\"auth\"]" <$authfile
    is "$status" "0" "jq from $authfile"

    expect_userpass="${RAMALAMA_LOGIN_USER}:${RAMALAMA_LOGIN_PASS}"
    actual_userpass=$(base64 -d <<<"$output")
    is "$actual_userpass" "$expect_userpass" "credentials stored in $authfile"


    # Now log out and make sure credentials are removed
    run_ramalama logout --authfile=$authfile $registry

    run jq -r '.auths' <$authfile
    is "$status" "0" "jq from $authfile"
    is "$output" "{}" "credentials removed from $authfile"
}

@test "ramalama login inconsistent authfiles" {
    ambiguous_file=${RAMALAMA_LOGIN_WORKDIR}/ambiguous-auth.json
    echo '{}' > $ambiguous_file # To make sure we are not hitting the “file not found” path

    run_ramalama 125 login --authfile "$ambiguous_file" --compat-auth-file "$ambiguous_file" localhost:5000
    assert "$output" =~ "Error: options for paths to the credential file and to the Docker-compatible credential file can not be set simultaneously"

    run_ramalama 125 logout --authfile "$ambiguous_file" --compat-auth-file "$ambiguous_file" localhost:5000
    assert "$output" =~ "Error: options for paths to the credential file and to the Docker-compatible credential file can not be set simultaneously"
}

# Some push tests
@test "ramalama push fail" {
    # Create an invalid authfile
    authfile=${RAMALAMA_LOGIN_WORKDIR}/auth-$(random_string 10).json
    rm -f $authfile

    wrong_auth=$(base64 <<<"baduser:wrongpassword")
    cat >$authfile <<EOF
{
    "auths": {
            "localhost:${RAMALAMA_LOGIN_REGISTRY_PORT}": {
                    "auth": "$wrong_auth"
            }
    }
}
EOF

    run_ramalama 125 push --authfile=$authfile \
        --tls-verify=false $IMAGE \
        localhost:${RAMALAMA_LOGIN_REGISTRY_PORT}/badpush:1
    is "$output" ".* checking whether a blob .* exists in localhost:${RAMALAMA_LOGIN_REGISTRY_PORT}/badpush: authentication required" \
       "auth error on push"
}

# END   primary ramalama login/push/pull tests
###############################################################################
# BEGIN cooperation with skopeo

# Skopeo helper - keep this separate, so we can test with different
# envariable settings
function _test_skopeo_credential_sharing() {
    registry=localhost:${RAMALAMA_LOGIN_REGISTRY_PORT}

    run_ramalama login "$@" --tls-verify=false \
               --username ${RAMALAMA_LOGIN_USER} \
               --password ${RAMALAMA_LOGIN_PASS} \
               $registry

    destname=skopeo-ok-$(random_string 10 | tr A-Z a-z)-ok
    echo "# skopeo copy ..."
    run skopeo copy "$@" \
        --format=v2s2 \
        --dest-tls-verify=false \
        containers-storage:$IMAGE \
        docker://$registry/$destname
    echo "$output"
    is "$status" "0" "skopeo copy - exit status"
    is "$output" ".*Copying blob .*"     "output of skopeo copy"
    is "$output" ".*Copying config .*"   "output of skopeo copy"
    is "$output" ".*Writing manifest .*" "output of skopeo copy"

    echo "# skopeo inspect ..."
    run skopeo inspect "$@" --tls-verify=false docker://$registry/$destname
    echo "$output"
    is "$status" "0" "skopeo inspect - exit status"

    got_name=$(jq -r .Name <<<"$output")
    is "$got_name" "$registry/$destname" "skopeo inspect -> Name"

    # Now try without a valid login; it should fail
    run_ramalama logout "$@" $registry
    echo "# skopeo inspect [with no credentials] ..."
    run skopeo inspect "$@" --tls-verify=false docker://$registry/$destname
    echo "$output"
    is "$status" "1" "skopeo inspect - exit status"
    is "$output" ".*: authentication required" \
       "auth error on skopeo inspect"
}

@test "ramalama login - shares credentials with skopeo - default auth file" {
    _test_skopeo_credential_sharing
}

@test "ramalama login - shares credentials with skopeo - via envariable" {
    authfile=${RAMALAMA_LOGIN_WORKDIR}/auth-$(random_string 10).json
    rm -f $authfile

    REGISTRY_AUTH_FILE=$authfile _test_skopeo_credential_sharing
    rm -f $authfile
}

@test "ramalama login - shares credentials with skopeo - via --authfile" {
    # Also test that command-line --authfile overrides envariable
    authfile=${RAMALAMA_LOGIN_WORKDIR}/auth-$(random_string 10).json
    rm -f $authfile

    fake_authfile=${RAMALAMA_LOGIN_WORKDIR}/auth-$(random_string 10).json
    rm -f $fake_authfile

    REGISTRY_AUTH_FILE=$authfile _test_skopeo_credential_sharing --authfile=$authfile

    if [ -e $fake_authfile ]; then
        die "REGISTRY_AUTH_FILE overrode command-line --authfile!"
    fi
    rm -f $authfile
}

# END   cooperation with skopeo
# END   actual tests
###############################################################################

# vim: filetype=sh
