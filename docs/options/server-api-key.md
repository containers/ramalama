####> This option file is used in:
####>   ramalama run, ramalama serve
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--api-key**=*key*
Require clients to present this API key on requests to the AI Model server.
Only supported by the llama.cpp runtime. The default is no authentication.

The key is handed to the server through the `LLAMA_API_KEY` environment
variable rather than on its command line, so it appears in neither the
`llama-server` nor the container engine arguments. Passing it as `--api-key`
does put it in ramalama's own arguments, where it is visible in the host
process table for as long as the command runs.

There are three ways to supply it, with different exposure:

| How | Where the key ends up |
| --- | --- |
| `--api-key <key>` | ramalama's own argv, so visible in `ps` output and in shell history |
| `ramalama.conf` | a file on disk; protect it with file permissions |
| `RAMALAMA_RUNTIMES__LLAMA_CPP__SERVER_API_KEY` | ramalama's environment, readable through `/proc/<pid>/environ` by the same user and by root, but absent from `ps` output and from disk |

Clients may present it as either an `Authorization: Bearer <key>` or an
`X-Api-Key: <key>` header; requests without a valid key get a `401`. The
`/health` and `/v1/health` endpoints and the web UI assets stay
public so that health checks keep working. Whether the model listing
(`/models`, `/v1/models`) is public depends on the llama.cpp version in the
image; do not rely on it being either way.

Generate a random key on the shell with:

```
KEY=$(openssl rand -hex 32)
```

The default can be set per-runtime in `ramalama.conf`:

```
[ramalama.runtimes.llama_cpp]
server_api_key = "..."
```

or through the matching environment variable, which overrides the file:

```
export RAMALAMA_RUNTIMES__LLAMA_CPP__SERVER_API_KEY="$KEY"
```

Caveats:

* With `--generate`, the key is written into the generated Quadlet, Kubernetes
  or Compose file in plaintext, because those files are read without ramalama
  in the picture. Treat the generated file as a secret.
* When the server runs in a container, the key is readable via
  `podman inspect` / `docker inspect` on the container.
* With `--webui on`, the web UI itself still loads, because its assets are
  public, but its API calls are rejected unless the UI is configured with the
  key.
* Not supported together with `--rag` or `--api llama-stack`: in both cases the
  port the user reaches is served by a helper that cannot present the key.
