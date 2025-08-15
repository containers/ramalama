#! /bin/bash

# shellcheck source=/dev/null
source "$VIRTUAL_ENV/bin/activate"

if [ $# -eq 0 ]; then
    exec bash
else
    exec "$@"
fi
