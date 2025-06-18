#!/bin/bash

if [ -z "${MODEL_PATH}" ]; then
    MODEL_PATH="/mnt/models/model.file"
fi

whisper-server \
    -tr \
    --model "${MODEL_PATH}" \
    --convert \
    --host "${HOST:=0.0.0.0}" \
    --port "${PORT:=8001}"
exit 0
