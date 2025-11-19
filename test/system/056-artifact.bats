#!/usr/bin/env bats

load helpers
load helpers.registry
load setup_suite

# bats test_tags=distro-integration
@test "ramalama convert artifact - basic functionality" {
    skip_if_nocontainer
    skip_if_docker
    # Requires the -rag images which are not available on these arches yet
    skip_if_ppc64le
    skip_if_s390x

    testmodel=$RAMALAMA_TMPDIR/testmodel
    artifact=artifact-test:latest
    run_ramalama ? rm ${artifact}

    echo "hello" > ${testmodel}
    run_ramalama convert --type artifact file://${testmodel} ${artifact}
    run_ramalama list
    is "$output" ".*artifact-test.*latest" "artifact was created and listed"

    # Verify it's actually an artifact by checking podman artifact ls
    run_podman artifact ls
    is "$output" ".*artifact-test.*latest" "artifact appears in podman artifact list"

    run_ramalama rm file://${testmodel}
    run_ramalama rm ${artifact}
    run_ramalama ls
    assert "$output" !~ ".*artifact-test" "artifact was removed"
}

@test "ramalama convert artifact - from ollama model" {
    skip_if_nocontainer
    skip_if_docker
    skip_if_ppc64le
    skip_if_s390x

    run_ramalama pull tiny
    run_ramalama convert --type artifact tiny artifact-tiny:latest
    run_ramalama list
    is "$output" ".*artifact-tiny.*latest" "artifact was created from ollama model"

    # Verify it's an artifact
    run_podman artifact ls
    is "$output" ".*artifact-tiny.*latest" "artifact appears in podman artifact list"

    run_ramalama rm artifact-tiny:latest
    assert "$output" !~ ".*artifact-tiny" "artifact was removed"
}

@test "ramalama convert artifact - with OCI target" {
    skip_if_nocontainer
    skip_if_docker
    skip_if_ppc64le
    skip_if_s390x

    local registry=localhost:${PODMAN_LOGIN_REGISTRY_PORT}
    local authfile=$RAMALAMA_TMPDIR/authfile.json
    start_registry
    run_ramalama login --authfile=$authfile \
	--tls-verify=false \
	--username ${PODMAN_LOGIN_USER} \
	--password ${PODMAN_LOGIN_PASS} \
	oci://$registry

    echo "test model" > $RAMALAMA_TMPDIR/testmodel
    run_ramalama convert --type artifact file://$RAMALAMA_TMPDIR/testmodel oci://$registry/artifact-test:1.0
    run_ramalama list
    is "$output" ".*$registry/artifact-test.*1.0" "OCI artifact was created"

    # Verify it's an artifact
    run_podman artifact ls
    is "$output" ".*$registry/artifact-test.*1.0" "OCI artifact appears in podman artifact list"

    run_ramalama rm file://$RAMALAMA_TMPDIR/testmodel
    run_ramalama rm oci://$registry/artifact-test:1.0
    run_podman artifact ls
    assert "$output" !~ ".*$registry/artifact-test" "OCI artifact was removed"
    stop_registry
}

@test "ramalama convert artifact - error handling" {
    skip_if_nocontainer

    # Test invalid type
    run_ramalama 2 convert --type invalid file://$RAMALAMA_TMPDIR/test oci://test
    is "$output" ".*error: argument --type: invalid choice: 'invalid'" "invalid type is rejected"

    # Test missing arguments
    run_ramalama 2 convert --type artifact
    is "$output" ".*ramalama convert: error: the following arguments are required: SOURCE, TARGET" "missing arguments are rejected"

    # Test with nocontainer
    run_ramalama 22 --nocontainer convert --type artifact file://$RAMALAMA_TMPDIR/test oci://test
    is "$output" "Error: convert command cannot be run with the --nocontainer option." "nocontainer is rejected for convert"
}

@test "ramalama push artifact - basic functionality" {
    skip_if_nocontainer
    skip_if_docker
    skip_if_ppc64le
    skip_if_s390x
    local registry=localhost:${PODMAN_LOGIN_REGISTRY_PORT}
    local authfile=$RAMALAMA_TMPDIR/authfile.json
    start_registry
    run_ramalama login --authfile=$authfile \
	--tls-verify=false \
	--username ${PODMAN_LOGIN_USER} \
	--password ${PODMAN_LOGIN_PASS} \
	oci://$registry

    run_ramalama ? rm oci://$registry/artifact-test-push:latest
    echo "test model" > $RAMALAMA_TMPDIR/testmodel

    run_ramalama convert --type artifact file://$RAMALAMA_TMPDIR/testmodel oci://$registry/artifact-test-push:latest
    run_ramalama list
    is "$output" ".*$registry/artifact-test-push.*latest" "artifact was pushed and listed"
    run_ramalama push --type artifact oci://$registry/artifact-test-push:latest

    # Verify it's an artifact
    run_podman artifact ls
    is "$output" ".*$registry/artifact-test-push" "pushed artifact appears in podman artifact list"

    run_ramalama rm oci://$registry/artifact-test-push:latest

    run_ramalama ls
    assert "$output" !~ ".*$registry/artifact-test-push" "pushed artifact was removed"

    echo "test model" > $RAMALAMA_TMPDIR/testmodel
    run_ramalama convert --type raw file://$RAMALAMA_TMPDIR/testmodel oci://$registry/test-image:latest
    run_ramalama push --type artifact oci://$registry/test-image:latest

    run_ramalama rm oci://$registry/test-image:latest
    assert "$output" !~ ".*test-image" "local image was removed"
    stop_registry
}

@test "ramalama list - includes artifacts" {
    skip_if_nocontainer
    skip_if_docker
    skip_if_ppc64le
    skip_if_s390x

    artifact="artifact-test:latest"
    run_podman ? podman artifact rm ${artifact}
    # Create a regular image
    echo "test model" > $RAMALAMA_TMPDIR/testmodel
    run_ramalama convert --type raw file://$RAMALAMA_TMPDIR/testmodel test-image

    # Create an artifact
    run_ramalama convert --type artifact file://$RAMALAMA_TMPDIR/testmodel ${artifact}

    run_ramalama list
    is "$output" ".*test-image.*latest" "regular image appears in list"
    is "$output" ".*artifact-test.*latest" "artifact appears in list"

    run_ramalama rm test-image:latest ${artifact}
    run_ramalama list
    assert "$output" !~ ".*test-image" "regular image was removed"
    run_podman artifact ls
    assert "$output" !~ ".*artifact-test" "artifact was removed"
}

@test "ramalama list - json output includes artifacts" {
    skip_if_darwin
    skip_if_nocontainer
    skip_if_docker
    skip_if_ppc64le
    skip_if_s390x

    echo "test model" > $RAMALAMA_TMPDIR/testmodel
    run_ramalama convert --type artifact file://$RAMALAMA_TMPDIR/testmodel artifact-test:latest

    run_ramalama list --json
    # Check that the artifact appears in JSON output
    name=$(echo "$output" | jq -r '.[].name')
    is "$name" ".*artifact-test.*latest" "artifact name in JSON output"

    # Check that it has required fields
    modified=$(echo "$output" | jq -r '.[0].modified')
    size=$(echo "$output" | jq -r '.[0].size')
    assert "$modified" != "" "artifact has modified field"
    assert "$size" != "" "artifact has size field"

    run_ramalama rm artifact-test:latest
    run_podman artifact ls
    assert "$output" !~ ".*artifact-test.*latest" "artifact was removed"
}

@test "ramalama convert - default type from config" {
    skip_if_nocontainer
    skip_if_docker
    skip_if_ppc64le
    skip_if_s390x

    run_ramalama ? rm test-config-artifact:latest
    # Create a temporary config with artifact as default
    local config_file=$RAMALAMA_TMPDIR/ramalama.conf
    cat > $config_file << EOF
[ramalama]
# Convert the MODEL to the specified OCI Object
convert_type = "artifact"
EOF

    echo "test model" > $RAMALAMA_TMPDIR/testmodel

    # Test with config file
    RAMALAMA_CONFIG=$config_file run_ramalama convert file://$RAMALAMA_TMPDIR/testmodel test-config-artifact:latest
    run_ramalama list
    is "$output" ".*test-config-artifact.*latest" "artifact was created with config default type"

    # Verify it's an artifact
    run_podman artifact ls
    is "$output" ".*test-config-artifact.*latest" "artifact appears in podman artifact list"

    run_ramalama rm test-config-artifact:latest
}

@test "ramalama convert - type precedence (CLI over config)" {
    skip_if_nocontainer
    skip_if_docker
    skip_if_ppc64le
    skip_if_s390x

    # Create a temporary config with artifact as default
    local config_file=$RAMALAMA_TMPDIR/ramalama.conf
    cat > $config_file << EOF
[ramalama]
# Convert the MODEL to the specified OCI Object
convert_type = "artifact"
EOF

    echo "test model" > $RAMALAMA_TMPDIR/testmodel

    # Test with CLI override
    RAMALAMA_CONFIG=$config_file run_ramalama convert --type raw file://$RAMALAMA_TMPDIR/testmodel test-cli-override
    run_ramalama list
    is "$output" ".*test-cli-override.*latest" "raw image was created despite config default"

    # Verify it's NOT an artifact (should be a regular image)
    run_podman artifact ls
    assert "$output" !~ ".*test-cli-override" "image does not appear in podman artifact list"

    run_ramalama rm test-cli-override
    assert "$output" !~ ".*test-cli-override" "image was removed"
}

@test "ramalama convert - all supported types" {
    skip_if_nocontainer
    skip_if_docker
    skip_if_ppc64le
    skip_if_s390x

    run_ramalama ? rm test-car:latest test-raw:latest
    echo "test model" > $RAMALAMA_TMPDIR/testmodel

    # Test car type
    run_ramalama convert --type car file://$RAMALAMA_TMPDIR/testmodel test-car:latest
    run_ramalama list
    is "$output" ".*test-car.*latest" "car type works"

    # Test raw type
    run_ramalama convert --type raw file://$RAMALAMA_TMPDIR/testmodel test-raw:latest
    run_ramalama list
    is "$output" ".*test-raw.*latest" "raw type works"

    # Verify artifacts vs images
    run_podman artifact ls
    assert "$output" !~ ".*test-car" "car does not appear in artifact list"
    assert "$output" !~ ".*test-raw" "raw does not appear in artifact list"

    # Clean up
    run_ramalama rm test-car:latest test-raw:latest
    assert "$output" !~ ".*test-car" "car was removed"
    assert "$output" !~ ".*test-raw" "raw was removed"
}

@test "ramalama push - all supported types" {
    skip_if_nocontainer
    skip_if_docker
    skip_if_ppc64le
    skip_if_s390x
    local registry=localhost:${PODMAN_LOGIN_REGISTRY_PORT}
    local authfile=$RAMALAMA_TMPDIR/authfile.json
    start_registry
    run_ramalama login --authfile=$authfile \
	--tls-verify=false \
	--username ${PODMAN_LOGIN_USER} \
	--password ${PODMAN_LOGIN_PASS} \
	oci://$registry

    echo "test model" > $RAMALAMA_TMPDIR/testmodel

    run_ramalama ? rm artifact-test:latest
    # Test artifact push
    run_ramalama convert --type artifact file://$RAMALAMA_TMPDIR/testmodel oci://$registry/artifact-test-push:latest
    run_ramalama list
    is "$output" ".*$registry/artifact-test-push.*latest" "convert artifact works"
    run_ramalama push --authfile=$authfile --tls-verify=false oci://$registry/artifact-test-push:latest

    # Test car push
    run_ramalama convert --type car file://$RAMALAMA_TMPDIR/testmodel oci://$registry/test-car-push:1.0
    run_ramalama list
    is "$output" ".*$registry/test-car-push.*1.0" "convert works"
    run_ramalama push --authfile=$authfile --tls-verify=false oci://$registry/test-car-push:1.0
    run_ramalama list
    is "$output" ".*$registry/test-car-push.*1.0" "car push works"

    # Test raw push
    run_ramalama convert --type raw file://$RAMALAMA_TMPDIR/testmodel oci://$registry/test-raw-push:1.1
    run_ramalama push --authfile=$authfile --tls-verify=false oci://$registry/test-raw-push:1.1
    run_ramalama list
    is "$output" ".*$registry/test-raw-push.*1.1" "raw push works"

    # Clean up
    run_ramalama rm file://$RAMALAMA_TMPDIR/testmodel oci://$registry/artifact-test-push:latest oci://$registry/test-car-push:1.0 oci://$registry/test-raw-push:1.1

    run_ramalama list
    assert "$output" !~ ".*$registry/artifact-test-push" "pushed artifact was removed"
    assert "$output" !~ ".*$registry/test-car-push" "pushed car was removed"
    assert "$output" !~ ".*$registry/test-raw-push" "pushed raw was removed"
    stop_registry
}

# bats test_tags=distro-integration
@test "ramalama artifact - large file handling" {
    skip_if_nocontainer
    skip_if_docker
    skip_if_ppc64le
    skip_if_s390x

    # Create a larger test file (1MB)
    dd if=/dev/zero of=$RAMALAMA_TMPDIR/large_model bs=1M count=1 2>/dev/null
    echo "test data" >> $RAMALAMA_TMPDIR/large_model

    run_ramalama convert --type artifact file://$RAMALAMA_TMPDIR/large_model large-artifact:latest
    run_ramalama list
    is "$output" ".*large-artifact.*latest" "large artifact was created"

    # Verify size is reasonable
    size=$(run_ramalama list --json | jq -r '.[0].size')
    assert [ "$size" -gt 1000000 ] "artifact size is at least 1MB"

    run_ramalama rm large-artifact
    run_ramalama ls
    assert "$output" !~ ".*large-artifact" "large artifact was removed"
}

@test "ramalama artifact - multiple files in artifact" {
    skip_if_nocontainer
    skip_if_docker
    skip_if_ppc64le
    skip_if_s390x

    # Create multiple test files
    echo "model data 1" > $RAMALAMA_TMPDIR/model1.gguf
    echo "model data 2" > $RAMALAMA_TMPDIR/model2.gguf
    echo "config data" > $RAMALAMA_TMPDIR/config.json

    # Create a tar archive to simulate a multi-file model
    tar -czf $RAMALAMA_TMPDIR/multi_model.tar.gz -C $RAMALAMA_TMPDIR model1.gguf model2.gguf config.json

    run_ramalama convert --type artifact file://$RAMALAMA_TMPDIR/multi_model.tar.gz multi-artifact
    run_ramalama list
    is "$output" ".*multi-artifact:latest" "multi-file artifact was created"

    # Verify it's an artifact
    run_podman artifact ls
    is "$output" ".*multi-artifact:latest" "multi-file artifact appears in podman artifact list"

    run_ramalama rm multi-artifact
    assert "$output" !~ ".*multi-artifact" "multi-file artifact was removed"
}

@test "ramalama artifact - concurrent operations" {
    skip_if_nocontainer
    skip_if_docker
    skip_if_ppc64le
    skip_if_s390x

    echo "test model 1" > $RAMALAMA_TMPDIR/testmodel1
    echo "test model 2" > $RAMALAMA_TMPDIR/testmodel2

    # Create two artifacts concurrently
    run_ramalama convert --type artifact file://$RAMALAMA_TMPDIR/testmodel1 concurrent-artifact1 &
    pid1=$!
    run_ramalama convert --type artifact file://$RAMALAMA_TMPDIR/testmodel2 concurrent-artifact2 &
    pid2=$!

    # Wait for both to complete
    wait $pid1
    wait $pid2

    run_ramalama list
    is "$output" ".*concurrent-artifact1:latest" "first concurrent artifact was created"
    is "$output" ".*concurrent-artifact2:latest" "second concurrent artifact was created"

    run_ramalama rm concurrent-artifact1 concurrent-artifact2
    assert "$output" !~ ".*concurrent-artifact1" "first concurrent artifact was removed"
    assert "$output" !~ ".*concurrent-artifact2" "second concurrent artifact was removed"
}

@test "ramalama artifact - error handling for invalid source" {
    skip_if_nocontainer
    skip_if_docker

    # Test with non-existent file
    run_ramalama 22 convert --type artifact file:///nonexistent/path/model.gguf test-artifact
    is "$output" ".*Error.*" "non-existent file is handled gracefully"

    # Test with directory instead of file
    mkdir -p $RAMALAMA_TMPDIR/testdir
    run_ramalama 22 convert --type artifact file://$RAMALAMA_TMPDIR/testdir test-artifact
    is "$output" ".*Error.*" "directory as source is handled gracefully"
}

@test "ramalama artifact - size reporting accuracy" {
    skip_if_nocontainer
    skip_if_docker
    skip_if_ppc64le
    skip_if_s390x

    # Create a file with known size
    echo "test data for size verification" > $RAMALAMA_TMPDIR/size_test_model
    expected_size=$(wc -c < $RAMALAMA_TMPDIR/size_test_model)

    run_ramalama convert --type artifact file://$RAMALAMA_TMPDIR/size_test_model size-test-artifact
    run_ramalama list --json
    reported_size=$(echo "$output" | jq -r '.[0].size')

    # Allow for some overhead in artifact storage
    assert [ "$reported_size" -ge "$expected_size" ] "reported size is at least the file size"
    assert [ "$reported_size" -lt "$((expected_size * 2))" ] "reported size is not excessively large"

    run_ramalama rm size-test-artifact
    assert "$output" !~ ".*size-test-artifact" "size test artifact was removed"
}

# bats test_tags=distro-integration
@test "ramalama config - convert_type setting" {
    skip_if_nocontainer
    skip_if_docker
    skip_if_ppc64le
    skip_if_s390x

    # Test default configuration
    local config_file=$RAMALAMA_TMPDIR/ramalama.conf
    cat > $config_file << EOF
[ramalama]
# Test configuration file
convert_type = "artifact"
EOF

    echo "test model" > $RAMALAMA_TMPDIR/testmodel

    artifact=config-test-artifact:latest
    # Test with config file
    RAMALAMA_CONFIG=$config_file run_ramalama convert file://$RAMALAMA_TMPDIR/testmodel ${artifact}
    run_ramalama list
    is "$output" ".*config-test-artifact.*latest" "artifact was created with config default"

    # Verify it's an artifact
    run_podman artifact ls
    is "$output" ".*config-test-artifact.*latest" "artifact appears in podman artifact list"

    run_ramalama rm ${artifact}
    assert "$output" !~ ".*config-test-artifact" "artifact was removed"
}

@test "ramalama config - convert_type validation" {
    skip_if_nocontainer

    # Test invalid convert_type in config
    local config_file=$RAMALAMA_TMPDIR/ramalama.conf
    cat > $config_file << EOF
[ramalama]
convert_type = "invalid_type"
EOF

    echo "test model" > $RAMALAMA_TMPDIR/testmodel

    # This should fail with invalid config
    RAMALAMA_CONFIG=${config_file} run_ramalama 22 convert file://$RAMALAMA_TMPDIR/testmodel test-invalid
    is "$output" ".*Error.*" "invalid convert_type in config is rejected"
}

@test "ramalama config - convert_type precedence" {
    skip_if_nocontainer
    skip_if_docker
    skip_if_ppc64le
    skip_if_s390x

    # Create config with artifact as default
    local config_file=$RAMALAMA_TMPDIR/ramalama.conf
    cat > $config_file << EOF
[ramalama]
convert_type = "artifact"
EOF

    echo "test model" > $RAMALAMA_TMPDIR/testmodel

    # Test CLI override of config
    RAMALAMA_CONFIG=$config_file run_ramalama convert --type raw file://$RAMALAMA_TMPDIR/testmodel cli-override-test
    run_ramalama list
    is "$output" ".*cli-override-test:latest" "CLI type override worked"

    # Verify it's NOT an artifact (should be raw)
    run_podman artifact ls
    assert "$output" !~ ".*cli-override-test" "CLI override created raw image, not artifact"

    run_ramalama rm cli-override-test
    assert "$output" !~ ".*cli-override-test" "image was removed"
}

@test "ramalama config - environment variable override" {
    skip_if_nocontainer
    skip_if_docker
    skip_if_ppc64le
    skip_if_s390x

    # Create config with artifact as default
    local config_file=$RAMALAMA_TMPDIR/ramalama.conf
    cat > $config_file << EOF
[ramalama]
convert_type = "artifact"
EOF

    echo "test model" > $RAMALAMA_TMPDIR/testmodel

    # Test environment variable override
    RAMALAMA_CONFIG=$config_file RAMALAMA_CONVERT_TYPE=raw run_ramalama convert file://$RAMALAMA_TMPDIR/testmodel env-override-test
    run_ramalama list
    is "$output" ".*env-override-test:latest" "environment variable override worked"

    # Verify it's NOT an artifact (should be raw)
    run_podman artifact ls
    assert "$output" !~ ".*env-override-test" "environment override created raw image, not artifact"

    run_ramalama rm env-override-test
    assert "$output" !~ ".*env-override-test" "image was removed"
}

# vim: filetype=sh
