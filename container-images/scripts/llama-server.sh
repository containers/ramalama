#!/bin/bash
if [ -n "${MODEL_CHAT_FORMAT}" ]; then
    CHAT_FORMAT="--chat_template ${MODEL_CHAT_FORMAT}"
fi

if [ -n ${MODEL_PATH} ]; then
    llama-server \
        --model ${MODEL_PATH} \
        --host ${HOST:=0.0.0.0} \
        --port ${PORT:=8001} \
        --gpu_layers ${GPU_LAYERS:=0} \
	${CHAT_FORMAT}
    exit 0
fi

echo "Please set a MODEL_PATH"
exit 1

