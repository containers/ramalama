####> This option file is used in:
####>   ramalama serve
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--tls-key-file**=*path*
PEM-encoded private key matching **--tls-cert-file**, only valid together with
it. In container mode the key is bind mounted read-only into the container at
`/mnt/tls/tls.key`.

The key must not be passphrase protected: the inference server runs
non-interactively and cannot prompt for one.
