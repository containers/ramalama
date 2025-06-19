#!/usr/bin/env bash

set -eo pipefail

# FIXME: enable bats-docker tests in TMT. Currently, they are not being run in
# CI jobs, but can be triggered manually using this script.
if [[ $# -eq 0 || $1 != "docker" && $1 != "nocontainer" ]]; then
    echo "Error: provide only one argument: 'docker'  or 'nocontainer'"
    exit 1
fi

set -x
TMT_TREE=${TMT_TREE:-$(git rev-parse --show-toplevel)}
pushd "$TMT_TREE"

if [[ $1 == "docker" ]]; then
    ./container_build.sh build ramalama
elif [[ $1 == "nocontainer" ]]; then
    ./container-images/scripts/build_llama_and_whisper.sh
fi
./.github/scripts/install-ollama.sh

set +e
tty
set -e

make bats-"$1"
popd
