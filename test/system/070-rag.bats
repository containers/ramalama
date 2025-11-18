#!/usr/bin/env bats

load helpers

# bats test_tags=distro-integration

@test "ramalama rag dryrun" {
    skip_if_nocontainer
    HTTPS_FILE=https://github.com/containers/ramalama/blob/main/README.md
    run_ramalama --dryrun rag $HTTPS_FILE quay.io/ramalama/myrag:1.2
    is "$output" ".*doc2rag --format qdrant /output $HTTPS_FILE " "Expected to see https command"
    assert "$output" !~ ".*--network none" "Expected to not use network"
    if not_docker; then
        assert "$output" !~ ".*--user.*" "Expected no --user option"
    else
        assert "$output" =~ ".*--user.*" "Expected --user option"
    fi
    run_ramalama --dryrun rag --format json $HTTPS_FILE quay.io/ramalama/myrag:1.2
    is "$output" ".*doc2rag --format json /output $HTTPS_FILE " "Expected to --format json option"
    run_ramalama --dryrun rag --format milvus $HTTPS_FILE quay.io/ramalama/myrag:1.2
    is "$output" ".*doc2rag --format milvus /output $HTTPS_FILE " "Expected to see --format milvus option"
    assert "$output" !~ ".*/docs.*" "Expected no /docs argument when no local files are provided"
    run_ramalama --debug --dryrun rag $HTTPS_FILE quay.io/ramalama/myrag:1.2
    is "$output" ".*doc2rag --debug" "Expected to run doc2rag with --debug"

    FILE=README.md
    run_ramalama --dryrun rag $FILE quay.io/ramalama/myrag:1.2
    is "$output" ".*-v ${PWD}/$FILE:/docs/$FILE" "Expected to see file volume mounted in"
    is "$output" ".*doc2rag --format qdrant /output /docs" "Expected to see doc2rag command"
    is "$output" ".*--pull missing" "only pull if missing"

    # Run with OCR
    run_ramalama --dryrun rag --format markdown --ocr $FILE quay.io/ramalama/myrag:1.2
    is "$output" ".*doc2rag --format markdown --ocr /output /docs" "Expected to see ocr flag"

    FILE_URL=file://${PWD}/README.md
    run_ramalama --dryrun rag $FILE_URL quay.io/ramalama/myrag:1.2
    is "$output" ".*-v ${PWD}/$FILE:/docs/$FILE" "Expected to see file volume mounted in"

    FILE=BOGUS
    run_ramalama 22 --dryrun rag $FILE quay.io/ramalama/myrag:1.2
    is "$output" "Error: BOGUS does not exist" "Throw error when file does not exist"
}

@test "ramalama rag" {
    skip_if_nocontainer
    run_ramalama 22 -q rag bogus quay.io/ramalama/myrag:1.2
    is "$output" "Error: bogus does not exist" "Expected failure"

    run_ramalama 22 -q rag README.md quay.io/ramalama/MYRAG:1.2
    is "$output" "Error: invalid reference format: repository name 'quay.io/ramalama/MYRAG:1.2' must be lowercase"
}

@test "ramalama run --rag" {
    skip_if_nocontainer
    run_ramalama --dryrun run --rag quay.io/ramalama/myrag:1.2 ollama://smollm:135m
    is "${lines[0]}" ".*llama-server" "Expected to run llama-server"
    is "${lines[0]}" ".*--port 8081" "Expected to run llama-server on port 8081"
    is "${lines[1]}" ".*quay.io/ramalama/.*-rag:" "Expected to use -rag image in separate container"
    is "${lines[1]}" ".*rag_framework serve" "Expected to run rag_framework in a separate container"
    is "${lines[1]}" ".*--port 8080" "Expected to run rag_framework on port 8080"
    if not_docker; then
       is "${lines[1]}" ".*--mount=type=image,source=quay.io/ramalama/myrag:1.2,destination=/rag,rw=true" "Expected RAG image to be mounted into separate container with rw=true for Podman"
       is "$output" ".*--pull missing.*" "Expected to use --pull missing"
       RAMALAMA_CONFIG=/dev/null run_ramalama --dryrun run --rag quay.io/ramalama/myrag:1.2 ollama://smollm:135m
       is "$output" ".*--pull newer.*" "Expected to use --pull newer"
    fi
    run_ramalama --dryrun run --image quay.io/ramalama/bogus --rag quay.io/ramalama/myrag:1.2 ollama://smollm:135m
    assert "$output" !~ ".*quay.io/ramalama/bogus-rag.*" "Expected to not use -rag image"

    run_ramalama --dryrun run --rag quay.io/ramalama/myrag:1.2 --rag-image quay.io/ramalama/rag-image:latest ollama://smollm:135m
    is "$output" ".*quay.io/ramalama/rag-image:latest.*" "Expected --rag-image to be used"

    run_ramalama --debug --dryrun run --rag quay.io/ramalama/myrag:1.2 --rag-image quay.io/ramalama/rag-image:latest ollama://smollm:135m
    is "$output" ".*rag_framework --debug serve" "Expected to run rag_framework with --debug"

    RAG_DIR=$(mktemp -d)
    run_ramalama --dryrun run --rag $RAG_DIR ollama://smollm:135m
    is "$output" ".*--mount=type=bind,source=$RAG_DIR,destination=/rag/vector.db.*" "Expected RAG dir to be mounted"
    rmdir $RAG_DIR
}

@test "ramalama rag README.md" {
    skip_if_nocontainer
    skip_if_ppc64le
    skip_if_s390x
    run_ramalama rag README.md https://github.com/containers/ramalama/blob/main/README.md https://github.com/containers/podman/blob/main/README.md quay.io/ramalama/myrag:1.2

    run_ramalama info
    engine=$(echo "$output" | jq --raw-output '.Engine.Name')
    run ${engine} rmi quay.io/ramalama/myrag:1.2
}

# vim: filetype=sh
