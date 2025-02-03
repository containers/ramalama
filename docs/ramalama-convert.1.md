% ramalama-convert 1

## NAME
ramalama\-convert - convert AI Models from local storage to OCI Image

## SYNOPSIS
**ramalama convert** [*options*] *model* [*target*]

## DESCRIPTION
Convert specified AI Model to an OCI Formatted AI Model

The model can be from RamaLama model storage in Huggingface, Ollama, or local model stored on disk.

## OPTIONS

#### **--help**, **-h**
Print usage message

#### **--network-mode**=*none*
sets the configuration for network namespaces when handling RUN instructions

#### **--type**=*raw* | *car*

type of OCI Model Image to convert.

| Type | Description                                                   |
| ---- | ------------------------------------------------------------- |
| car  | Includes base image with the model stored in a /models subdir |
| raw  | Only the model and a link file model.file to it stored at /   |

## EXAMPLE

Generate an oci model out of an Ollama model.
```
$ ramalama convert ollama://tinyllama:latest oci://quay.io/rhatdan/tiny:latest
Building quay.io/rhatdan/tiny:latest...
STEP 1/2: FROM scratch
STEP 2/2: COPY sha256:2af3b81862c6be03c769683af18efdadb2c33f60ff32ab6f83e42c043d6c7816 /model
--> Using cache 69db4a10191c976d2c3c24da972a2a909adec45135a69dbb9daeaaf2a3a36344
COMMIT quay.io/rhatdan/tiny:latest
--> 69db4a10191c
Successfully tagged quay.io/rhatdan/tiny:latest
69db4a10191c976d2c3c24da972a2a909adec45135a69dbb9daeaaf2a3a36344
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-push(1)](ramalama-push.1.md)**

## HISTORY
Aug 2024, Originally compiled by Eric Curtin <ecurtin@redhat.com>
