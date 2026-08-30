####> This option file is used in:
####>   ramalama sandbox goose, ramalama sandbox opencode, ramalama sandbox pi
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--internal-network**
Use a private network without internet access for the sandbox (agent and model
server containers).
Only available when --url is not specified (i.e. when ramalama starts its own model server).
The network is created automatically and removed when the sandbox exits. If a previous
run was killed, the network may remain; remove it first (podman network rm NAME /
docker network rm NAME).
