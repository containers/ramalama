####> This fragment is pulled into options/server-api-key.md and
####> options/rag-api-key.md with @@include. It is not an @@option file,
####> so the header above is maintained by hand.
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
