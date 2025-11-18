#!/usr/bin/env bash

# Default to running the sd command if no arguments provided
if [ $# -eq 0 ]; then
    exec sd
else
    exec "$@"
fi
