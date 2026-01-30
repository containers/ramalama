#!/usr/bin/env bash
# shellcheck disable=SC1091

source /opt/intel/oneapi/setvars.sh > /dev/null

if [ $# -gt 0 ]; then
    exec "$@"
elif tty -s; then
    exec /bin/bash
fi
