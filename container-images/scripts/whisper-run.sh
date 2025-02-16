#!/bin/bash

if [ -n "${MODEL_PATH}" ]; then
    whisper-server \
	-tr \
	--model "${MODEL_PATH}" \
	--convert \
	--host "${HOST:=0.0.0.0}" \
	--port "${PORT:=8001}"
    exit 0
fi

echo "Please set a MODEL_PATH"
exit 1
