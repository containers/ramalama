####> This option file is used in:
####>   ramalama bench, ramalama perplexity, ramalama run, ramalama sandbox goose, ramalama sandbox opencode, ramalama serve
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--env**=

Set environment variables inside the container.

This option allows arbitrary environment variables that are available for the
process to be launched inside the container. If an environment variable is
specified without a value, the container engine checks the host environment
for a value and sets the variable only if it is set on the host.

