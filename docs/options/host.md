####> This option file is used in:
####>   ramalama sandbox goose, ramalama sandbox opencode, ramalama sandbox pi, ramalama serve
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--host**="127.0.0.1"
IP address for the model server to listen on. Defaults to "127.0.0.1", so the
served model is only reachable from the local machine. To expose it on the
network, set this to a wildcard address such as "0.0.0.0" (IPv4) or "::"
(dual-stack).
