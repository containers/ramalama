####> This option file is used in:
####>   ramalama rag
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--api-key**=*key*
Require this API key on the llama.cpp servers this command starts. The
default is no authentication.

Each of those servers publishes a port on the host for as long as the
conversion runs, so without a key anyone on the host can use them. `doc2rag`
presents the key on every request it makes to them; it listens on no port of
its own, so nothing here requires a key of you.

The key reaches the servers through the `LLAMA_API_KEY` environment variable
rather than on their command line, so it appears in neither the `llama-server`
nor the container engine arguments. Passing it as `--api-key` does put it in
ramalama's own arguments, where it is visible in the host process table for as
long as the command runs; supplying it through `ramalama.conf` or the
environment keeps it out of `ps` output. However supplied, it is readable via
`podman inspect` / `docker inspect` on the containers.

@@include options/api-key-sources.md
