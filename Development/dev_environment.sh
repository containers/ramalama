#!/bin/bash

# Make ssh key
if [ ! -f $(echo $HOME)/.ssh/ramalama_container ]; then 
    ssh-keygen -t ed25519 -b 4096 -N "" -f $(echo $HOME)/.ssh/ramalama_container; 
fi

# Config new ssh key
cat ~/.ssh/config | grep -q ramalama_container || cat << 'EOF' >> ~/.ssh/config

Host ramalama_container
    HostName 127.0.0.1
    IdentityFile ~/.ssh/ramalama_container
    IdentitiesOnly yes
    User podman
    Port 2222
EOF

# Build podman development container
podman build -t ramalama-python .

# Run podman development container 
podman run --rm \
    --sig-proxy=false \
    --userns=keep-id \
    --pid=host \
    --security-opt=label=disable \
    --security-opt=unmask=ALL \
    --systemd=false \
    -a STDOUT \
    -a STDERR \
    -v ../:/home/podman/ramalama:z \
    -v $(echo $HOME)/.local/share/ramalama/:/home/podman/.local/share/ramalama/:z \
    -v /run/podman:/run/podman \
    -v $(echo $HOME)/.ssh/ramalama_container.pub:/home/podman/.ssh/ramalama_container.pub:z \
    -v $(echo $HOME)/.ssh/ramalama_container.pub:/home/podman/.ssh/authorized_keys:z \
    -u podman \
    -p 2222:2222 \
    $(test -e /dev/fuse && echo "--device=/dev/fuse") \
    $(test -e /dev/dri && echo "--device=/dev/dri") \
    $(lspci | grep ' VGA ' | grep -q NVIDIA && echo --device=nvidia.com/gpu=all) \
    --name ramalama-python \
    localhost/ramalama-python:latest &

# rm 127.0.0.1:2222 from known_host
sed -i '/\[127.0.0.1\]:2222/d' $(echo $HOME)/.ssh/known_hosts

# ssh into container
if command -v code 2>&1 >/dev/null; then
    code --remote ssh-remote+ramalama_container /home/podman/ramalama && podman rm -f ramalama-python

elif command -v theia 2>&1 >/dev/null; then
    theia --remote ssh-remote+ramalama_container /home/podman/ramalama && podman rm -f ramalama-python

elif command -v codium 2>&1 >/dev/null; then
    codium --remote ssh-remote+ramalama_container /home/podman/ramalama && podman rm -f ramalama-python
fi