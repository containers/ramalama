####> This option file is used in:
####>   ramalama bench, ramalama perplexity, ramalama run, ramalama sandbox goose, ramalama sandbox opencode, ramalama serve
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--engine-args**="*args*"
Add *args* to the **podman** or **docker** invocation (before the container image), after RamaLama-generated options and model bind mounts.
The option may be specified multiple times; each value is shell-split and all tokens are passed to the engine in order.
Use for extra **--mount** flags (for example multimodal projector files) or other engine-specific options. Shell-quoting rules match **--runtime-args**.
