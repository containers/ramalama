#!/bin/bash

echo "$(id -un):10000:2000" > /etc/subuid
echo "$(id -un):10000:2000" > /etc/subgid

if [ $# -gt 0 ]; then
    exec "$@"
else
    exec /bin/bash
fi
