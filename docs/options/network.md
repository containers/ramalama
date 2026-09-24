####> This option file is used in:
####>   ramalama bench, ramalama perplexity, ramalama run, ramalama sandbox goose, ramalama sandbox opencode, ramalama sandbox pi, ramalama serve
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--network**=*none*
set the network mode for the container

For `ramalama sandbox`, the value `internal` creates a private network without
internet access for the sandbox (agent and model server containers). It is only
available when --url is not specified (i.e. when ramalama starts its own model
server). The network is created automatically and removed when the sandbox
exits. If a previous run was killed, the network may remain; remove it first
(podman network rm NAME / docker network rm NAME).
