% ramalama-sandbox-pi 1

## NAME
ramalama\-sandbox\-pi - run Pi in a sandbox, backed by a local AI Model

## SYNOPSIS
**ramalama sandbox pi** [*options*] [*model* ...]

## DESCRIPTION
Run Pi in a container, connected to a local model server also running
in a container. Pi uses the model for reasoning and tool calling.

When a single model is specified, the server loads that model directly.
When no model and the url is given the command gets the list of models from the
model server and takes the first model or fails without a model.
When multiple models are specified, the server starts in router mode
using llama.cpp's --models-dir, dynamically loading and unloading models.
When no models and no url the default `http://localhost:{port}` is used to
get the first model. If there is no server or no model then it falls back to
start a model server in router mode where all GGUF models in the store are served.

Use **--prompt** to pass instructions for non-interactive processing.
Commands may also be passed via stdin.

Two containers are started: a model server (llama-server) and the agent
container. They communicate via container networking. When the agent session
exits, the model server container is automatically stopped and removed.

If the url is not given then two containers are started: a model server (llama-server) and the agent
container. They communicate via container networking. When the agent session
exits, the model server container is automatically stopped and removed.
Otherwise only the agent container starts using the given url for the openai compatible model server.

## OPTIONS


[//]: # (BEGIN included file options/api-key.md)
#### **--api-key**
OpenAI-compatible API key.
Can also be set via the RAMALAMA_API_KEY environment variable.

[//]: # (END   included file options/api-key.md)


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
ramalama sandbox pi granite

# Force Vulkan backend
ramalama sandbox pi --backend vulkan granite

# Force ROCm backend on AMD GPU
ramalama sandbox pi --backend rocm granite
```

[//]: # (END   included file options/backend.md)


[//]: # (BEGIN included file options/cache-reuse.md)
#### **--cache-reuse**=*BYTES*
Minimum chunk size (in bytes) to attempt reusing from the cache via KV shifting.
When omitted, llama-server uses its built-in default.

[//]: # (END   included file options/cache-reuse.md)


[//]: # (BEGIN included file options/ctx-size.md)
#### **--ctx-size**, **-c**
size of the prompt context. This option is also available as **--max-model-len**. Applies to llama.cpp and vllm regardless of alias (default: 0, 0 = loaded from model)

[//]: # (END   included file options/ctx-size.md)


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


[//]: # (BEGIN included file options/help.md)
#### **--help**, **-h**
Show this help message and exit

[//]: # (END   included file options/help.md)


[//]: # (BEGIN included file options/host.md)
#### **--host**="::"
IP address for llama.cpp to listen on. Defaults to "::" (dual-stack) on systems with IPv6 support, "0.0.0.0" on IPv4-only systems.

[//]: # (END   included file options/host.md)


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
ramalama sandbox pi --image ghcr.io/ggml-org/llama.cpp:full-vulkan MODEL
```

[//]: # (END   included file options/image.md)


[//]: # (BEGIN included file options/keep-groups.md)
#### **--keep-groups**
pass --group-add keep-groups to podman (default: False)
If GPU device on host system is accessible to user via group access, this option leaks the groups into the container.

[//]: # (END   included file options/keep-groups.md)


[//]: # (BEGIN included file options/logfile.md)
#### **--logfile**=*path*
Log output to a file

[//]: # (END   included file options/logfile.md)


[//]: # (BEGIN included file options/max-tokens.md)
#### **--max-tokens**=*integer*
Maximum number of tokens to generate. Set to 0 for unlimited output (default: 0).
This parameter is mapped to the appropriate runtime-specific parameter:
- llama.cpp: `-n` parameter
- MLX: `--max-tokens` parameter
- vLLM: `--max-model-len` parameter (mapped via `ctx_size`)

[//]: # (END   included file options/max-tokens.md)


[//]: # (BEGIN included file options/model-draft.md)
#### **--model-draft**

A draft model is a smaller, faster model that helps accelerate the decoding
process of larger, more complex models, like Large Language Models (LLMs). It
works by generating candidate sequences of tokens that the larger model then
verifies and refines. This approach, often referred to as speculative decoding,
can significantly improve the speed of inferencing by reducing the number of
times the larger model needs to be invoked.

Use --runtime-args to pass the other draft model related parameters.
Make sure the sampling parameters like top_k on the web UI are set correctly.

[//]: # (END   included file options/model-draft.md)


[//]: # (BEGIN included file options/models-max.md)
#### **--models-max**=*integer*
Maximum number of models to load concurrently in router mode (default: 4).
Only used when invoked in router mode (zero or multiple models).

[//]: # (END   included file options/models-max.md)


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


[//]: # (BEGIN included file options/pi-image.md)
#### **--pi-image**=*IMAGE*
Pi agent container image. The default is `quay.io/ramalama/pi-agent`
tagged for the RamaLama minor release.

[//]: # (END   included file options/pi-image.md)


[//]: # (BEGIN included file options/port.md)
#### **--port**, **-p**
port for AI Model server to listen on. It must be available. If not specified,
a free port in the 8080-8180 range is selected, starting with 8080.

The default can be overridden in the `ramalama.conf` file.

[//]: # (END   included file options/port.md)


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


[//]: # (BEGIN included file options/prompt.md)
#### **--prompt**
Instructions for the sandbox agent to process non-interactively.

[//]: # (END   included file options/prompt.md)


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


[//]: # (BEGIN included file options/spec-draft-n-max.md)
#### **--spec-draft-n-max**=*N*
Maximum number of tokens to draft per speculative decoding step (default: 3).

[//]: # (END   included file options/spec-draft-n-max.md)


[//]: # (BEGIN included file options/spec-draft-n-min.md)
#### **--spec-draft-n-min**=*N*
Minimum number of draft tokens to use for speculative decoding (default: 0).

[//]: # (END   included file options/spec-draft-n-min.md)


[//]: # (BEGIN included file options/spec-draft-p-min.md)
#### **--spec-draft-p-min**=*P*
Minimum speculative decoding probability, greedy threshold (default: 0.0).

[//]: # (END   included file options/spec-draft-p-min.md)


[//]: # (BEGIN included file options/spec-type.md)
#### **--spec-type**=*TYPES*
Comma-separated list of speculative decoding types to enable.
Available types: draft-simple, draft-eagle3, draft-mtp, ngram-simple,
ngram-map-k, ngram-map-k4v, ngram-mod, ngram-cache.
When omitted, speculative decoding is disabled.

[//]: # (END   included file options/spec-type.md)


[//]: # (BEGIN included file options/temp.md)
#### **--temp**="0.8"
Temperature of the response from the AI Model.
llama.cpp explains this as:

    The lower the number is, the more deterministic the response.

    The higher the number is the more creative the response is, but more likely to hallucinate when set too high.

    Usage: Lower numbers are good for virtual assistants where we need deterministic responses. Higher numbers are good for roleplay or creative tasks like editing stories.

[//]: # (END   included file options/temp.md)


[//]: # (BEGIN included file options/thinking.md)
#### **--thinking**=*BOOL*
Enable or disable thinking mode in reasoning models.
Maps to `--reasoning on` or `--reasoning off` in llama-server.
When omitted, llama-server defaults to `auto`.

[//]: # (END   included file options/thinking.md)


[//]: # (BEGIN included file options/threads.md)
#### **--threads**, **-t**
Maximum number of cpu threads to use.
The default is to use half the cores when more than 4 cores are available; otherwise, the default is 4 threads.

[//]: # (END   included file options/threads.md)


[//]: # (BEGIN included file options/tls-verify.md)
#### **--tls-verify**=*true*
Require HTTPS and verify certificates when contacting OCI registries

[//]: # (END   included file options/tls-verify.md)


[//]: # (BEGIN included file options/url.md)
#### **--url**=URL
The host to send requests to (default: http://localhost:8080)

[//]: # (END   included file options/url.md)


[//]: # (BEGIN included file options/webui.md)
#### **--webui**=*on* | *off*
Enable or disable the web UI for the served model (enabled by default). When set to "on" (the default), the web interface is properly initialized. When set to "off", the `--no-webui` option is passed to the llama-server command to disable the web interface.

[//]: # (END   included file options/webui.md)


[//]: # (BEGIN included file options/workdir.md)
#### **--workdir**, **-w**
Local directory to mount into the sandbox container at /work

[//]: # (END   included file options/workdir.md)

## EXAMPLES

Run the Pi agent with default settings:
```
ramalama sandbox pi qwen3:4b
```

Run the Pi agent in router mode (serve all models in the store):
```
ramalama sandbox pi
```

Run the Pi agent with multiple models in router mode:
```
ramalama sandbox pi qwen3:4b granite-code:3b
```

Run the Pi agent with a custom image:
```
ramalama sandbox pi --pi-image myimage:v1 qwen3:4b
```

Turn off thinking mode in the model the agent is connecting to (may result in faster responses):
```
ramalama sandbox pi --thinking=off qwen3:4b
```

Start an interactive session with access to a local directory:
```
ramalama sandbox pi -w ./src qwen3:4b
```

Request the agent to perform actions non-interactively:
```
ramalama sandbox pi -w ./src qwen3:4b --prompt "Please analyze the source code in the current directory"
```

Send instructions to the agent via stdin:
```
echo "What is the speed of light in meters per second?" | ramalama sandbox pi qwen3:4b
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-run(1)](ramalama-run.1.md)**, **[ramalama-serve(1)](ramalama-serve.1.md)**, **[ramalama-sandbox(1)](ramalama-sandbox.1.md)**

## HISTORY
Jun 2026, Originally compiled by Brian <brian@ramalama>
