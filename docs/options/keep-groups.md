####> This option file is used in:
####>   ramalama bench, ramalama perplexity, ramalama run, ramalama sandbox goose, ramalama sandbox opencode, ramalama serve
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--keep-groups**
pass --group-add keep-groups to podman (default: False)
If GPU device on host system is accessible to user via group access, this option leaks the groups into the container.
