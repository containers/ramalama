####> This option file is used in:
####>   ramalama perplexity, ramalama run, ramalama sandbox goose, ramalama sandbox opencode, ramalama serve
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--chat-template-file**=*path*
Path to a chat template file on the host. The file is mounted into the container and passed to the runtime (e.g. llama-server), so you can use a custom or fixed template without redownloading the model. Only valid when using containers.
