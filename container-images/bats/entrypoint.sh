#!/bin/bash

echo "$(id -un):10000:2000" > /etc/subuid
echo "$(id -un):10000:2000" > /etc/subgid

while [ $# -gt 0 ]; do
    if [[ "$1" =~ = ]]; then
        # shellcheck disable=SC2163
        export "$1"
        shift
    else
        break
    fi
done

if [ $# -gt 0 ]; then
    exec "$@"
else
    exec /bin/bash
fi
