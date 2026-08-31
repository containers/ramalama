% ramalama-bench 1

## NAME
ramalama\-bench - benchmark specified AI Model

## SYNOPSIS
**ramalama bench** [*options*] *model* [arg ...]


[//]: # (BEGIN included file options/model-transports.md)
## MODEL TRANSPORTS

| Transports    | Prefix | Web Site                                            |
| ------------- | ------ | --------------------------------------------------- |
| URL based     | https://, http://, file:// | `https://web.site/ai.model`, `file:///tmp/ai.model`|
| HuggingFace   | huggingface://, hf://, hf.co/ | [`huggingface.co`](https://www.huggingface.co)|
| ModelScope    | modelscope://, ms:// | [`modelscope.cn`](https://modelscope.cn/)|
| Ollama        | ollama:// | [`ollama.com`](https://www.ollama.com)|
| rlcr          | rlcr://   | [`ramalama.com`](https://registry.ramalama.com) |
| OCI Container Registries | oci://, docker:// | [`opencontainers.org`](https://opencontainers.org)||||Examples: [`quay.io`](https://quay.io),  [`Docker Hub`](https://docker.io),[`Artifactory`](https://artifactory.com)|
| Hosted API Providers | openai:// | [`api.openai.com`](https://api.openai.com)|
Models can be specified using a shortname (e.g. `tiny`) which is resolved via `shortnames.conf`, or with an explicit transport prefix such as `huggingface://`, `oci://`, `ollama://`, `https://`, `http://`, or `file://`. Models in the `<org>/<model>` format without a prefix are pulled from Hugging Face.

The default transport can be overridden in the `ramalama.conf` file or via the `RAMALAMA_TRANSPORT` environment variable. For example, `export RAMALAMA_TRANSPORT=huggingface` changes RamaLama to use the Hugging Face transport for unqualified model names.

URL support means if a model is on a web site or even on your local system, you can run it directly.

[//]: # (END   included file options/model-transports.md)

## OPTIONS


[//]: # (BEGIN included file options/authfile.md)
#### **--authfile**=*path*
Path to the authentication file for OCI registries.

[//]: # (END   included file options/authfile.md)


[//]: # (BEGIN included file options/backend.md)
#### **--backend**=*auto* | vulkan | rocm | cuda | sycl | openvino | cann | musa

GPU backend to use for inference (default: auto).

Available backends depend on the detected GPU hardware.

**auto** (default): Automatically selects the preferred backend based on your GPU:
- **AMD GPUs**: vulkan (Linux/macOS) or rocm (Windows)
- **NVIDIA GPUs**: cuda
- **Intel GPUs**: vulkan (Linux/macOS) or sycl (Windows); openvino available as explicit option
- **Ascend NPUs**: cann
- **MUSA GPUs**: musa
- **No GPU**: vulkan (CPU fallback)

**Platform-specific behavior**:
- On **Linux/macOS**, Vulkan provides broad compatibility and is preferred for AMD and Intel GPUs
- On **Windows**, vulkan is not supported on WSL2, so vendor-specific backends (rocm, sycl) are preferred

**Explicit backend selection**:
- **vulkan**: Use Vulkan-based inference (compatible with AMD, Intel, and CPU)
- **rocm**: Use AMD ROCm backend (AMD GPUs only)
- **cuda**: Use NVIDIA CUDA backend (NVIDIA GPUs only)
- **sycl**: Use Intel SYCL/oneAPI backend (Intel GPUs only)
- **openvino**: Use Intel OpenVINO backend (Intel GPUs only); uses `quay.io/ramalama/openvino`
- **cann**: Use Huawei CANN backend (Ascend NPUs only); uses `quay.io/ramalama/cann`
- **musa**: Use Moore Threads MUSA backend (MUSA GPUs only); uses `quay.io/ramalama/musa`

**Available choices**: The allowed values for `--backend` are dynamically determined based on
your detected GPU hardware. For example, on a system with an AMD GPU, only `auto`, `vulkan`,
and `rocm` are available.

**Configuration**: The default can be overridden in the `ramalama.conf` file or via the
RAMALAMA_BACKEND environment variable.

Examples:
```
# Use auto-detection (default)
ramalama bench granite

# Force Vulkan backend
ramalama bench --backend vulkan granite

# Force ROCm backend on AMD GPU
ramalama bench --backend rocm granite
```

[//]: # (END   included file options/backend.md)


[//]: # (BEGIN included file options/device.md)
#### **--device**
Add a host device to the container. Optional permissions parameter can
be used to specify device permissions by combining r for read, w for
write, and m for mknod(2).

Example: --device=/dev/dri/renderD128:/dev/xvdc:rwm

The device specification is passed directly to the underlying container engine. See documentation of the supported container engine for more information.

Pass '--device=none' to explicitly add no device to the container, e.g., for
running a CPU-only performance comparison.

[//]: # (END   included file options/device.md)


[//]: # (BEGIN included file options/engine-args.md)
#### **--engine-args**="*args*"
Add *args* to the **podman** or **docker** invocation (before the container image), after RamaLama-generated options and model bind mounts.
The option may be specified multiple times; each value is shell-split and all tokens are passed to the engine in order.
Use for extra **--mount** flags (for example multimodal projector files) or other engine-specific options. Shell-quoting rules match **--runtime-args**.

[//]: # (END   included file options/engine-args.md)


[//]: # (BEGIN included file options/env.md)
#### **--env**=

Set environment variables inside the container.

This option allows arbitrary environment variables that are available for the
process to be launched inside the container. If an environment variable is
specified without a value, the container engine checks the host environment
for a value and sets the variable only if it is set on the host.


[//]: # (END   included file options/env.md)


[//]: # (BEGIN included file options/format.md)
#### **--format**
Set the output format of the benchmark results. Options include json and table (default: table).

[//]: # (END   included file options/format.md)


[//]: # (BEGIN included file options/help.md)
#### **--help**, **-h**
Show this help message and exit

[//]: # (END   included file options/help.md)


[//]: # (BEGIN included file options/image.md)
#### **--image**=IMAGE
OCI container image to run with specified AI model. RamaLama defaults to using
images based on the accelerator it discovers and the selected `--backend`.
For example: `quay.io/ramalama/ramalama`. See the table below for all default images.
The default image tag is based on the minor version of the RamaLama package.
Version 0.24.0 of RamaLama pulls an image with a `:0.24` tag from the quay.io/ramalama OCI repository. The --image option overrides this default.

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
ramalama bench --image ghcr.io/ggml-org/llama.cpp:full-vulkan MODEL
```

[//]: # (END   included file options/image.md)


[//]: # (BEGIN included file options/keep-groups.md)
#### **--keep-groups**
pass --group-add keep-groups to podman (default: False)
If GPU device on host system is accessible to user via group access, this option leaks the groups into the container.

[//]: # (END   included file options/keep-groups.md)


[//]: # (BEGIN included file options/name.md)
#### **--name**, **-n**
Name of the container to run the Model in.

[//]: # (END   included file options/name.md)


[//]: # (BEGIN included file options/ncmoe.md)
#### **--ncmoe**
Keep the Mixture of Experts (MoE) weights of the first N layers in the CPU.

[//]: # (END   included file options/ncmoe.md)


[//]: # (BEGIN included file options/network.md)
#### **--network**=*none*
set the network mode for the container

[//]: # (END   included file options/network.md)


[//]: # (BEGIN included file options/ngl.md)
#### **--ngl**
Number of layers to store in VRAM: a number, `auto`, or `all`.
When omitted, llama-server defaults to `auto`.

[//]: # (END   included file options/ngl.md)


[//]: # (BEGIN included file options/oci-runtime.md)
#### **--oci-runtime**

Override the default OCI runtime used to launch the container. Container
engines like Podman and Docker, have their own default oci runtime that they
use. Using this option RamaLama will override these defaults.

On Nvidia based GPU systems, RamaLama defaults to using the
`nvidia-container-runtime`. Use this option to override this selection.

[//]: # (END   included file options/oci-runtime.md)


[//]: # (BEGIN included file options/privileged.md)
#### **--privileged**
By default, RamaLama containers are unprivileged (=false) and cannot, for
example, modify parts of the operating system. This is because by de‐
fault a container is only allowed limited access to devices. A "privi‐
leged" container is given the same access to devices as the user launch‐
ing the container, with the exception of virtual consoles (/dev/tty\d+)
when running in systemd mode (--systemd=always).

A privileged container turns off the security features that isolate the
container from the host. Dropped Capabilities, limited devices, read-
only mount points, Apparmor/SELinux separation, and Seccomp filters are
all disabled. Due to the disabled security features, the privileged
field should almost never be set as containers can easily break out of
confinement.

Containers running in a user namespace (e.g., rootless containers) can‐
not have more privileges than the user that launched them.

[//]: # (END   included file options/privileged.md)


[//]: # (BEGIN included file options/pull.md)
#### **--pull**=*policy*
Pull image policy. The default is **missing**.

- **always**: Always pull the image and throw an error if the pull fails.
- **missing**: Only pull the image when it does not exist in the local containers storage. Throw an error if no image is found and the pull fails.
- **never**: Never pull the image but use the one from the local containers storage. Throw an error when no image is found.
- **newer**: Pull if the image on the registry is newer than the one in the local containers storage. An image is considered to be newer when the digests are different. Comparing the time stamps is prone to errors. Pull errors are suppressed if a local image was found.

[//]: # (END   included file options/pull.md)


[//]: # (BEGIN included file options/runtime-args.md)
#### **--runtime-args**="*args*"
Add *args* to the runtime (llama.cpp or vllm) invocation.

[//]: # (END   included file options/runtime-args.md)


[//]: # (BEGIN included file options/seed.md)
#### **--seed**=
Specify a seed rather than using a random seed for model interaction.

[//]: # (END   included file options/seed.md)


[//]: # (BEGIN included file options/selinux.md)
#### **--selinux**=*true*
Enable SELinux container separation (default: `true`)

[//]: # (END   included file options/selinux.md)


[//]: # (BEGIN included file options/threads.md)
#### **--threads**, **-t**
Maximum number of cpu threads to use.
The default is to use half the cores when more than 4 cores are available; otherwise, the default is 4 threads.

[//]: # (END   included file options/threads.md)


[//]: # (BEGIN included file options/tls-verify.md)
#### **--tls-verify**=*true*
Require HTTPS and verify certificates when contacting OCI registries

[//]: # (END   included file options/tls-verify.md)

## DESCRIPTION
Benchmark specified AI Model.

## EXAMPLES

```
ramalama bench granite3-moe
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Jan 2025, Originally compiled by Eric Curtin <ecurtin@redhat.com>
