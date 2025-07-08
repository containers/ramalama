#! /bin/bash

# shellcheck source=/dev/null
source /.venv/bin/activate

VERSION_REF="heads/main"
PACKAGE_SPEC="ramalama-stack"
if [ -n "${RAMALAMA_STACK_VERSION}" ]; then
    VERSION_REF="refs/tags/v${RAMALAMA_STACK_VERSION}"
    PACKAGE_SPEC="ramalama-stack==${RAMALAMA_STACK_VERSION}"
fi

# hack that should be removed when the following bug is addressed
# https://github.com/containers/ramalama-stack/issues/53
BASE_URL="https://raw.githubusercontent.com/containers/ramalama-stack/${VERSION_REF}/src/ramalama_stack"
curl -fL --create-dirs --output ~/.llama/providers.d/remote/inference/ramalama.yaml "${BASE_URL}/providers.d/remote/inference/ramalama.yaml"
curl -fL --create-dirs --output /etc/ramalama/ramalama-run.yaml "${BASE_URL}/ramalama-run.yaml"

# install the ramalama-stack package
uv pip install "${PACKAGE_SPEC}"

if [ $# -eq 0 ]; then
    exec bash
else
    exec "$@"
fi
