#!/bin/bash

echo "$(id -u):1:4294967294" > /etc/subuid
echo "$(id -g):1:4294967294" > /etc/subgid

if [ $# -gt 0 ]; then
    exec "$@"
else
    exec /bin/bash
fi
