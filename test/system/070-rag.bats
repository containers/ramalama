#!/usr/bin/env bats

load helpers

# bats test_tags=distro-integration

@test "ramalama dryrun" {
    skip_if_nocontainer
    HTTPS_FILE=https://github.com/containers/ramalama/blob/main/README.md
    run_ramalama --dryrun rag $HTTPS_FILE quay.io/ramalama/myrag:1.2
    is "$output" ".*doc2rag --format qdrant /output /docs $HTTPS_FILE " "Expected to see https command"
    assert "$output" !~ ".*--network none" "Expected to not use network"
    run_ramalama --dryrun rag --format json $HTTPS_FILE quay.io/ramalama/myrag:1.2
    is "$output" ".*doc2rag --format json /output /docs $HTTPS_FILE " "Expected to --format json option"

    FILE=README.md
    run_ramalama --dryrun rag $FILE quay.io/ramalama/myrag:1.2
    is "$output" ".*-v ${PWD}/$FILE:/docs/$FILE" "Expected to see file volume mounted in"
    is "$output" ".*doc2rag --format qdrant /output /docs " "Expected to doc2rag command"
    is "$output" ".*--pull missing" "only pull if missing"

    # Run with OCR
    run_ramalama --dryrun rag --format markdown --ocr $FILE quay.io/ramalama/myrag:1.2
    is "$output" ".*doc2rag --format markdown /output /docs --ocr" "Expected to see ocr flag"

    FILE_URL=file://${PWD}/README.md
    run_ramalama --dryrun rag $FILE_URL quay.io/ramalama/myrag:1.2
    is "$output" ".*-v ${PWD}/$FILE:/docs/$FILE" "Expected to see file volume mounted in"

    FILE=BOGUS
    run_ramalama 22 --dryrun rag $FILE quay.io/ramalama/myrag:1.2
    is "$output" "Error: BOGUS does not exist" "Throw error when file does not exist"
}

@test "ramalama rag" {
    skip_if_nocontainer
    skip_if_docker
    skip "FIXME, need updated images with latest doc2rag to turn back on"
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
    run_ramalama --image quay.io/ramalama/bogus --dryrun run --rag quay.io/ramalama/myrag:1.2 ollama://smollm:135m
    assert "$output" !~ ".*quay.io/ramalama/bogus-rag.*" "Expected to not use -rag image"

    run_ramalama info
    engine=$(echo "$output" | jq --raw-output '.Engine.Name')
    run ${engine} rmi quay.io/ramalama/myrag:1.2
}

# vim: filetype=sh
