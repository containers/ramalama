% ramalama-convert 1

## NAME
ramalama\-convert - convert AI Models from local storage to OCI Image

## SYNOPSIS
**ramalama convert** [*options*] *model* [*target*]

## DESCRIPTION
Convert specified AI Model to an OCI Formatted AI Model

The model can be from RamaLama model storage in Huggingface, Ollama, or a local model stored on disk. Converting from an OCI model is not supported.

Note: The convert command must be run with containers. Use of the --nocontainer option is not allowed.

## OPTIONS

#### **--gguf**=*Q2_K* | *Q3_K_S* | *Q3_K_M* | *Q3_K_L* | *Q4_0* | *Q4_K_S* | *Q4_K_M* | *Q5_0* | *Q5_K_S* | *Q5_K_M* | *Q6_K* | *Q8_0* 

Convert Safetensor models into a GGUF with the specified quantization format. To learn more about model quantization, read llama.cpp documentation:
https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/README.md

#### **--help**, **-h**
Print usage message

#### **--network**=*none*
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

Generate and run an oci model with a quantized GGUF converted from Safetensors.
```
$ ramalama --image quay.io/ramalama/ramalama-rag convert --gguf Q4_K_M hf://ibm-granite/granite-3.2-2b-instruct oci://quay.io/kugupta/granite-3.2-q4-k-m:latest
Converting /Users/kugupta/.local/share/ramalama/models/huggingface/ibm-granite/granite-3.2-2b-instruct to quay.io/kugupta/granite-3.2-q4-k-m:latest...
Building quay.io/kugupta/granite-3.2-q4-k-m:latest...
$ ramalama run oci://quay.io/kugupta/granite-3.2-q4-k-m:latest
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-push(1)](ramalama-push.1.md)**

## HISTORY
Aug 2024, Originally compiled by Eric Curtin <ecurtin@redhat.com>
