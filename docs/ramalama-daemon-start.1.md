% ramalama-daemon-start 1

## NAME
ramalama\-daemon\-start - prepare and start a RamaLama REST daemon

## SYNOPSIS
**ramalama daemon start** [*options*]

## DESCRIPTION
Prepares and starts a new RamaLama daemon. When containers are enabled (the
default), **start** launches the daemon inside a container with the model store
mounted and publishes the host port. With **--nocontainer**, **start** runs the
daemon directly on the host by invoking **ramalama daemon run**.

## OPTIONS


[//]: # (BEGIN included file options/help.md)
#### **--help**, **-h**
Show this help message and exit

[//]: # (END   included file options/help.md)


[//]: # (BEGIN included file options/host.md)
#### **--host**="::"
IP address for service to listen on. Defaults to the value from
`ramalama.conf` (typically "::" on dual-stack systems, "0.0.0.0" on IPv4-only
systems).

[//]: # (END   included file options/host.md)

When **daemon start** runs the daemon in a container, this value is used as the host
IP for the published port mapping (`-p [host:]port:8080`). Wildcard addresses
(`::`, `0.0.0.0`) publish on all host interfaces. The daemon process inside the
container listens on all interfaces.

With **--nocontainer**, this value is the address the daemon binds on the host.


[//]: # (BEGIN included file options/image.md)
#### **--image**=IMAGE
OCI container image to run with specified AI model. RamaLama defaults to using
images based on the accelerator it discovers and the selected `--backend`.
For example: `quay.io/ramalama/ramalama`. See the table below for all default images.
The default image tag is based on the minor version of the RamaLama package.
Version 0.23.0 of RamaLama pulls an image with a `:0.23` tag from the quay.io/ramalama OCI repository. The --image option overrides this default.

The default can be overridden in the `ramalama.conf` file or via the
RAMALAMA_IMAGE environment variable. `export RAMALAMA_IMAGE=quay.io/ramalama/aiimage:1.2` tells
RamaLama to use the `quay.io/ramalama/aiimage:1.2` image.

**Note**: The `--backend` option provides a higher-level way to select the appropriate image
based on GPU type. Use `--backend` to select vulkan, rocm, cuda, sycl, or openvino backends, which will
automatically choose the correct image. Use `--image` only when you need to override the image
selection entirely.

Accelerated images:

| Backend / Accelerator   | Image                      |
| ------------------------| -------------------------- |
|  CPU, Vulkan            | quay.io/ramalama/ramalama  |
|  ROCm (AMD)             | quay.io/ramalama/rocm      |
|  CUDA (NVIDIA)          | quay.io/ramalama/cuda      |
|  Intel GPU (sycl)       | quay.io/ramalama/intel-gpu |
|  Intel GPU (openvino)   | quay.io/ramalama/openvino  |
|  Asahi (Apple Silicon)  | quay.io/ramalama/asahi     |
|  CANN (Ascend)          | quay.io/ramalama/cann      |
|  MUSA (Moore Threads)   | quay.io/ramalama/musa      |

Upstream llama.cpp "full" images from `ghcr.io/ggml-org/llama.cpp` are also supported.
RamaLama automatically detects the image type and adjusts the container CLI accordingly.

```
ramalama daemon start --image ghcr.io/ggml-org/llama.cpp:full-vulkan MODEL
```

[//]: # (END   included file options/image.md)


[//]: # (BEGIN included file options/port.md)
#### **--port**, **-p**
port for AI Model server to listen on. It must be available. If not specified,
a free port in the 8080-8180 range is selected, starting with 8080.

The default can be overridden in the `ramalama.conf` file.

[//]: # (END   included file options/port.md)

When **daemon start** runs in a container, this is the published host port mapped
to port 8080 in the container.


[//]: # (BEGIN included file options/pull.md)
#### **--pull**=*policy*
Pull image policy. The default is **missing**.

- **always**: Always pull the image and throw an error if the pull fails.
- **missing**: Only pull the image when it does not exist in the local containers storage. Throw an error if no image is found and the pull fails.
- **never**: Never pull the image but use the one from the local containers storage. Throw an error when no image is found.
- **newer**: Pull if the image on the registry is newer than the one in the local containers storage. An image is considered to be newer when the digests are different. Comparing the time stamps is prone to errors. Pull errors are suppressed if a local image was found.

[//]: # (END   included file options/pull.md)

## EXAMPLES

Start the daemon in a container (default), publishing port 8080:

```shell
ramalama daemon start --port 8080
```

Start the daemon on the host without a container:

```shell
ramalama --nocontainer daemon start --host 127.0.0.1 --port 8080
```

Publish only on localhost when running in a container:

```shell
ramalama daemon start --host 127.0.0.1 --port 8080
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-daemon(1)](ramalama-daemon.1.md)**, **[ramalama-daemon-run(1)](ramalama-daemon-run.1.md)**, **[ramalama-serve(1)](ramalama-serve.1.md)**

## HISTORY
Aug 2026, Split from ramalama-daemon(1)
