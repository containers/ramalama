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


[//]: # (BEGIN included file options/engine-args.md)
#### **--engine-args**="*args*"
Add *args* to the **podman** or **docker** invocation (before the container image), after RamaLama-generated options and model bind mounts.
The option may be specified multiple times; each value is shell-split and all tokens are passed to the engine in order.
Use for extra **--mount** flags (for example multimodal projector files) or other engine-specific options. Shell-quoting rules match **--runtime-args**.

[//]: # (END   included file options/engine-args.md)

#### **--gguf**=*Q2_K* | *Q3_K_S* | *Q3_K_M* | *Q3_K_L* | *Q4_0* | *Q4_K_S* | *Q4_K_M* | *Q5_0* | *Q5_K_S* | *Q5_K_M* | *Q6_K* | *Q8_0* 

Convert Safetensor models into a GGUF with the specified quantization format. To learn more about model quantization, read llama.cpp documentation:
https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/README.md


[//]: # (BEGIN included file options/help.md)
#### **--help**, **-h**
Show this help message and exit

[//]: # (END   included file options/help.md)

#### **--image**=IMAGE
Image to use for model quantization when converting to GGUF format (when the `--gguf` option has been specified). The image must have the
`llama-quantize` executable available on the `PATH`. Defaults to the appropriate `ramalama` image based on available accelerators. If no
accelerators are available, the current `quay.io/ramalama/ramalama` image will be used.


[//]: # (BEGIN included file options/network.md)
#### **--network**=*none*
set the network mode for the container

[//]: # (END   included file options/network.md)


[//]: # (BEGIN included file options/pull.md)
#### **--pull**=*policy*
Pull image policy. The default is **missing**.

- **always**: Always pull the image and throw an error if the pull fails.
- **missing**: Only pull the image when it does not exist in the local containers storage. Throw an error if no image is found and the pull fails.
- **never**: Never pull the image but use the one from the local containers storage. Throw an error when no image is found.
- **newer**: Pull if the image on the registry is newer than the one in the local containers storage. An image is considered to be newer when the digests are different. Comparing the time stamps is prone to errors. Pull errors are suppressed if a local image was found.

[//]: # (END   included file options/pull.md)

#### **--tools-image**=IMAGE
Image to use when converting to GGUF format (when the `--gguf` option has been specified). The image must have the `llama-convert-hf-to-gguf` script
executable and available in the `PATH`. The script is available from the `llama.cpp` GitHub repo. Defaults to the current
`quay.io/ramalama/ramalama-tools` image.

#### **--type**="artifact" | *raw* | *car*

Convert the MODEL to the specified OCI Object

| Type     | Description                                                   |
| -------- | ------------------------------------------------------------- |
| artifact | Store AI Models as artifacts                                  |
| car      | Traditional OCI image including base image with the model stored in a /models subdir |
| raw      | Traditional OCI image including only the model and a link file `model.file` pointed at it stored at /   |

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
$ ramalama convert --gguf Q4_K_M hf://ibm-granite/granite-3.2-2b-instruct oci://quay.io/kugupta/granite-3.2-q4-k-m:latest
Converting /Users/kugupta/.local/share/ramalama/models/huggingface/ibm-granite/granite-3.2-2b-instruct to quay.io/kugupta/granite-3.2-q4-k-m:latest...
Building quay.io/kugupta/granite-3.2-q4-k-m:latest...
$ ramalama run oci://quay.io/kugupta/granite-3.2-q4-k-m:latest
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-push(1)](ramalama-push.1.md)**

## HISTORY
Aug 2024, Originally compiled by Eric Curtin <ecurtin@redhat.com>
