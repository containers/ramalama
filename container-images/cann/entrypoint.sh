#!/usr/bin/env bash

export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH}

cann_in_sys_path=/usr/local/Ascend/ascend-toolkit
cann_in_user_path=$HOME/Ascend/ascend-toolkit
if [ -f "${cann_in_sys_path}/set_env.sh" ]; then
    source ${cann_in_sys_path}/set_env.sh;
elif [ -f "${cann_in_user_path}/set_env.sh" ]; then
    source "$HOME/Ascend/ascend-toolkit/set_env.sh";
else
    echo "No Ascend Toolkit found"; \
fi

exec "$@"
