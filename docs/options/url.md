####> This option file is used in:
####>   ramalama sandbox goose, ramalama sandbox opencode, ramalama sandbox pi
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--url**=URL
The host to send requests to (default: http://localhost:8080).

When the URL points at localhost (the host's loopback, e.g. a `ramalama serve`
container or any local OpenAI-compatible process), the agent container is wired to
reach that loopback server without requiring it to be exposed on a
container-reachable interface. On native Linux the agent shares the host network
namespace and reaches the server directly as localhost. On VM-backed engines
(podman machine / Docker Desktop on macOS and Windows) the localhost host is
rewritten to `host.containers.internal` / `host.docker.internal`, which the VM's
proxy forwards to the host's loopback.
