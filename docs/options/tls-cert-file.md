####> This option file is used in:
####>   ramalama serve
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--tls-cert-file**=*path*
Serve the REST API over HTTPS instead of HTTP, using the PEM-encoded
certificate at *path*. Requires **--tls-key-file**.

The certificate is handed to the inference server, which terminates TLS
itself. In container mode it is bind mounted read-only into the container at
`/mnt/tls/tls.crt`, and the generated quadlet, Kubernetes YAML and Compose
configurations mount it the same way.

If *path* contains an intermediate chain as well as the leaf certificate,
concatenate them in the file, leaf first.

Not supported together with **--api llama-stack** or **--rag**, and not
supported by the mlx runtime, whose server has no TLS support.
