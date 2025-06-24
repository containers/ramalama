#!/bin/bash

echo "$(id -u):10000:100000" > /etc/subuid
echo "$(id -g):10000:100000" > /etc/subgid

if [ $# -gt 0 ]; then
    exec "$@"
else
    exec /bin/bash
fi
