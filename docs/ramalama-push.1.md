% ramalama-push 1

## NAME
ramalama\-push - push AI Models from local storage to remote registries

## SYNOPSIS
**ramalama push** [*options*] *model* [*target*]

## DESCRIPTION
Push specified AI Model (OCI-only at present)

## OPTIONS

#### **--help**, **-h**
Print usage message

## EXAMPLE

Push and OCI model to registry
```
$ ramalama push oci://quay.io/rhatdan/tiny:latest
Pushing quay.io/rhatdan/tiny:latest...
Getting image source signatures
Copying blob e0166756db86 skipped: already exists
Copying config ebe856e203 done   |
Writing manifest to image destination
```

Generate an oci model out of an Ollama model and push to registry
```
$ ramalama push ollama://tinyllama:latest oci://quay.io/rhatdan/tiny:latest
Building quay.io/rhatdan/tiny:latest...
STEP 1/2: FROM scratch
STEP 2/2: COPY sha256:2af3b81862c6be03c769683af18efdadb2c33f60ff32ab6f83e42c043d6c7816 /model
--> Using cache 69db4a10191c976d2c3c24da972a2a909adec45135a69dbb9daeaaf2a3a36344
COMMIT quay.io/rhatdan/tiny:latest
--> 69db4a10191c
Successfully tagged quay.io/rhatdan/tiny:latest
69db4a10191c976d2c3c24da972a2a909adec45135a69dbb9daeaaf2a3a36344
Pushing quay.io/rhatdan/tiny:latest...
Getting image source signatures
Copying blob e0166756db86 skipped: already exists
Copying config 69db4a1019 done   |
Writing manifest to image destination
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Aug 2024, Originally compiled by Eric Curtin <ecurtin@redhat.com>
