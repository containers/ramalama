#!/usr/bin/env bash

if [ -z ${HOME} ]
then
  export HOME=/home/llama-user
fi

# Create Home directory
if [ ! -d "${HOME}" ]
then
  mkdir -p "${HOME}"
fi

# Create User ID
if ! whoami &> /dev/null
then
  if [ -w /etc/passwd ] && [ -w /etc/group ]
  then
    echo "${USER_NAME:-llama-user}:x:$(id -u):0:${USER_NAME:-llama-user} user:${HOME}:/bin/bash" >> /etc/passwd
    echo "${USER_NAME:-llama-user}:x:$(id -u):" >> /etc/group
    render_group="$(cat /etc/group | grep 'render:x')"
    video_group="$(cat /etc/group | grep 'video:x')"
    render_group_new="${render_group}${USER_NAME:-llama-user}"
    video_group_new="${video_group}${USER_NAME:-llama-user}"
    sed "s|${render_group}|${render_group_new}|g" /etc/group > /tmp/group
    cat /tmp/group > /etc/group
    sed "s|${video_group}|${video_group_new}|g" /etc/group > /tmp/group
    cat /tmp/group > /etc/group
  fi
fi

# Configure Z shell
if [ ! -f ${HOME}/.zshrc ]
then
  (echo "source /opt/intel/oneapi/setvars.sh") > ${HOME}/.zshrc
fi

# Configure Bash shell
if [ ! -f ${HOME}/.bashrc ]
then
  (echo "source /opt/intel/oneapi/setvars.sh") > ${HOME}/.bashrc
fi

source /opt/intel/oneapi/setvars.sh

exec "$@"
