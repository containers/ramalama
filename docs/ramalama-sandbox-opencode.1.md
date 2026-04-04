% ramalama-sandbox-opencode 1

## NAME
ramalama\-sandbox\-opencode - run OpenCode in a sandbox, backed by a local AI Model

## SYNOPSIS
**ramalama sandbox opencode** [*options*] *model* [arg ...]

## DESCRIPTION
Run OpenCode in a container, connected to a local model server also running
in a container. OpenCode uses the model for reasoning and tool calling.

When run with no arguments after the model, an interactive TUI session is
launched. If one or more arguments are provided, they are passed to the agent
as instructions to process non-interactively. Commands may also be passed via
stdin.

Two containers are started: a model server (llama-server) and the agent
container. They communicate via container networking. When the agent session
exits, the model server container is automatically stopped and removed.

## OPTIONS

#### **--authfile**=*password*
Path of the authentication file for OCI registries

#### **--backend**=*auto* | vulkan | rocm | cuda | sycl | openvino
GPU backend to use for inference (default: auto).

Available backends depend on the detected GPU hardware.

**auto** (default): Automatically selects the preferred backend based on your GPU:
- **AMD GPUs**: vulkan (Linux/macOS) or rocm (Windows)
- **NVIDIA GPUs**: cuda
- **Intel GPUs**: vulkan (Linux/macOS) or sycl (Windows); openvino available as explicit option
- **No GPU**: vulkan (CPU fallback)

**Platform-specific behavior**:
- On **Linux/macOS**, Vulkan provides broad compatibility and is preferred for AMD and Intel GPUs
- On **Windows**, vulkan is not supported on WSL2, so vendor-specific backends (rocm, sycl) are preferred

**Explicit backend selection**:
- **vulkan**: Use Vulkan-based inference (compatible with AMD, Intel, and CPU)
- **rocm**: Use AMD ROCm backend (AMD GPUs only)
- **cuda**: Use NVIDIA CUDA backend (NVIDIA GPUs only)
- **sycl**: Use Intel SYCL/oneAPI backend (Intel GPUs only)
- **openvino**: Use Intel OpenVINO backend (Intel GPUs only); uses `ghcr.io/ggml-org/llama.cpp:full-openvino`

**Available choices**: The allowed values for `--backend` are dynamically determined based on
your detected GPU hardware. For example, on a system with an AMD GPU, only `auto`, `vulkan`,
and `rocm` are available.

**Configuration**: The default can be overridden in the `ramalama.conf` file or via the
RAMALAMA_BACKEND environment variable.

Examples:
```
# Use auto-detection (default)
ramalama serve granite

# Force Vulkan backend
ramalama serve --backend vulkan granite

# Force ROCm backend on AMD GPU
ramalama serve --backend rocm granite
```

#### **--cache-reuse**=256
Min chunk size to attempt reusing from the cache via KV shifting

#### **--ctx-size**, **-c**
Size of the prompt context. This option is also available as **--max-model-len**. Applies to llama.cpp and vLLM regardless of alias (default: 0, 0 = loaded from model).

#### **--device**
Add a host device to the container. Optional permissions parameter can
be used to specify device permissions by combining r for read, w for
write, and m for mknod(2).

Example: --device=/dev/dri/renderD128:/dev/xvdc:rwm

The device specification is passed directly to the underlying container engine. See documentation of the supported container engine for more information.

Pass '--device=none' to explicitly add no device to the container, e.g. for
running a CPU-only performance comparison.

#### **--env**=

Set environment variables inside of the container.

This option allows arbitrary environment variables that are available for the
process to be launched inside of the container. If an environment variable is
specified without a value, the container engine checks the host environment
for a value and set the variable only if it is set on the host.

#### **--help**, **-h**
show this help message and exit

#### **--host**="0.0.0.0"
IP address for llama.cpp to listen on.

#### **--image**=IMAGE
OCI container image to run with specified AI model. RamaLama defaults to using
images based on the accelerator it discovers. For example:
`quay.io/ramalama/ramalama`. See the table below for all default images.
The default image tag is based on the minor version of the RamaLama package.
Version 0.18.0 of RamaLama pulls an image with a `:0.18` tag from the quay.io/ramalama OCI repository. The --image option overrides this default.

The default can be overridden in the `ramalama.conf` file or via the
RAMALAMA_IMAGE environment variable. `export RAMALAMA_IMAGE=quay.io/ramalama/aiimage:1.2` tells
RamaLama to use the `quay.io/ramalama/aiimage:1.2` image.

Accelerated images:

| Accelerator             | Image                      |
| ------------------------| -------------------------- |
|  CPU, Apple             | quay.io/ramalama/ramalama  |
|  HIP_VISIBLE_DEVICES    | quay.io/ramalama/rocm      |
|  CUDA_VISIBLE_DEVICES   | quay.io/ramalama/cuda      |
|  ASAHI_VISIBLE_DEVICES  | quay.io/ramalama/asahi     |
|  INTEL_VISIBLE_DEVICES  | quay.io/ramalama/intel-gpu |
|  ASCEND_VISIBLE_DEVICES | quay.io/ramalama/cann      |
|  MUSA_VISIBLE_DEVICES   | quay.io/ramalama/musa      |

Upstream llama.cpp "full" images from `ghcr.io/ggml-org/llama.cpp` are also supported.
RamaLama automatically detects the image type and adjusts the container CLI accordingly.

```
ramalama serve --image ghcr.io/ggml-org/llama.cpp:full-vulkan MODEL
```

#### **--keep-groups**
pass --group-add keep-groups to podman (default: False)
If GPU device on host system is accessible to user via group access, this option leaks the groups into the container.

#### **--logfile**=*path*
Log output to a file

#### **--max-tokens**=*integer*
Maximum number of tokens to generate. Set to 0 for unlimited output (default: 0).
This parameter is mapped to the appropriate runtime-specific parameter:
- llama.cpp: `-n` parameter
- MLX: `--max-tokens` parameter
- vLLM: `--max-tokens` parameter

#### **--model-draft**

A draft model is a smaller, faster model that helps accelerate the decoding
process of larger, more complex models, like Large Language Models (LLMs). It
works by generating candidate sequences of tokens that the larger model then
verifies and refines. This approach, often referred to as speculative decoding,
can significantly improve the speed of inferencing by reducing the number of
times the larger model needs to be invoked.

Use --runtime-args to pass the other draft model related parameters.
Make sure the sampling parameters like top_k on the web UI are set correctly.

#### **--name**, **-n**
Name of the container to run the Model in.

#### **--network**=*""*
set the network mode for the container

#### **--ngl**
number of GPU layers, 0 means CPU inferencing, 999 means use max layers (default: -1)
The default, -1, means use whatever is automatically deemed appropriate (0 or 999)

#### **--oci-runtime**

Override the default OCI runtime used to launch the container. Container
engines like Podman and Docker have their own default OCI runtime that they
use. Using this option, RamaLama will override these defaults.

On NVIDIA-based GPU systems, RamaLama defaults to using the
`nvidia-container-runtime`. Use this option to override this selection.

#### **--opencode-image**=*IMAGE*
OpenCode container image

#### **--port**, **-p**
port for AI Model server to listen on. It must be available. If not specified,
a free port in the 8080-8180 range is selected, starting with 8080.

The default can be overridden in the `ramalama.conf` file.

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

#### **--pull**=*policy*

- **always**: Always pull the image and throw an error if the pull fails.
- **missing**: Only pull the image when it does not exist in the local containers storage. Throw an error if no image is found and the pull fails.
- **never**: Never pull the image but use the one from the local containers storage. Throw an error when no image is found.
- **newer**: Pull if the image on the registry is newer than the one in the local containers storage. An image is considered to be newer when the digests are different. Comparing the time stamps is prone to errors. Pull errors are suppressed if a local image was found.

#### **--runtime-args**="*args*"
Add *args* to the runtime (llama.cpp or vllm) invocation.

#### **--seed**=
Specify a seed rather than using a random seed.

#### **--selinux**=*true*
Enable SELinux container separation

#### **--temp**="0.8"
Temperature of the response from the AI Model.
llama.cpp explains this as:

    The lower the number is, the more deterministic the response.

    The higher the number is the more creative the response is, but more likely to hallucinate when set too high.

	Usage: Lower numbers are good for virtual assistants where we need deterministic responses. Higher numbers are good for roleplay or creative tasks like editing stories

#### **--thinking**=*true*
Enable or disable thinking mode in reasoning models

#### **--threads**, **-t**
Maximum number of CPU threads to use.
The default is to use half the cores available on this system for the number of threads.

#### **--tls-verify**=*true*
require HTTPS and verify certificates when contacting OCI registries

#### **--webui**=*on* | *off*
Enable or disable the web UI for the served model (enabled by default). When set to "on" (the default), the web interface is properly initialized. When set to "off", the `--no-webui` option is passed to the llama-server command to disable the web interface.

#### **--workdir**, **-w**
Local directory to mount into the sandbox container at /work

## EXAMPLES

Run the OpenCode agent with default settings:
```
ramalama sandbox opencode qwen3:4b
```

Run the OpenCode agent with a custom image:
```
ramalama sandbox opencode --opencode-image ghcr.io/anomalyco/opencode:v1.3.0 qwen3:4b
```

Turn off thinking mode in the model the agent is connecting to (may result in faster responses):
```
ramalama sandbox opencode --thinking=off qwen3:4b
```

Start an interactive session with access to a local directory:
```
ramalama sandbox opencode -w ./src qwen3:4b
```

Request the agent to perform actions non-interactively:
```
ramalama sandbox opencode -w ./src qwen3:4b Please analyze the source code in the current directory
```

Send instructions to the agent via stdin:
```
echo "What is the speed of light in meters per second?" | ramalama sandbox opencode qwen3:4b
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-run(1)](ramalama-run.1.md)**, **[ramalama-serve(1)](ramalama-serve.1.md)**, **[ramalama-sandbox(1)](ramalama-sandbox.1.md)**

## HISTORY
Mar 2026, Originally compiled by Mike Bonnet <mikeb@redhat.com>
