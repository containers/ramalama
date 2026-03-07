% ramalama-agent 1

## NAME
ramalama\-agent - run an AI agent backed by a local AI Model

## SYNOPSIS
**ramalama agent** [*options*] [arg ...]

## DESCRIPTION
Run the Goose AI agent (https://github.com/block/goose) in a container,
connected to a local model server also running in a container. The agent
uses the model for reasoning and tool calling.

When run with no arguments, an interactive Goose session is launched. If one
or more arguments are provided, they are passed to Goose as instructions to
process non-interactively. Commands may also be passed via stdin.

Two containers are started: a model server (llama-server) and the Goose
agent. They communicate via container networking. When the Goose session
exits, the model server container is automatically stopped and removed.

## OPTIONS

#### **--agent-image**=*image*
Agent container image to use (default: ghcr.io/block/goose)

#### **--authfile**=*password*
Path of the authentication file for OCI registries

#### **--cache-reuse**=256
Min chunk size to attempt reusing from the cache via KV shifting

#### **--ctx-size**, **-c**
size of the prompt context. This option is also available as **--max-model-len**. Applies to llama.cpp and vllm regardless of alias (default: 0, 0 = loaded from model)

#### **--device**
Add a host device to the container. Optional permissions parameter can
be used to specify device permissions by combining r for read, w for
write, and m for mknod(2).

Example: --device=/dev/dri/renderD128:/dev/xvdc:rwm

The device specification is passed directly to the underlying container engine. See documentation of the supported container engine for more information.

Pass '--device=none' explicitly add no device to the container, eg for
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
Version 0.17.1 of RamaLama pulls an image with a `:0.17` tag from the quay.io/ramalama OCI repository. The --image option overrides this default.

The default can be overridden in the `ramalama.conf` file or via the
RAMALAMA_IMAGE environment variable. `export RAMALAMA_IMAGE=quay.io/ramalama/aiimage:1.2` tells
RamaLama to use the `quay.io/ramalama/aiimage:1.2` image.

Accelerated images:

| Accelerator             | Image                      |
| ----------------------- | -------------------------- |
|  CPU, Apple             | quay.io/ramalama/ramalama  |
|  HIP_VISIBLE_DEVICES    | quay.io/ramalama/rocm      |
|  CUDA_VISIBLE_DEVICES   | quay.io/ramalama/cuda      |
|  ASAHI_VISIBLE_DEVICES  | quay.io/ramalama/asahi     |
|  INTEL_VISIBLE_DEVICES  | quay.io/ramalama/intel-gpu |
|  ASCEND_VISIBLE_DEVICES | quay.io/ramalama/cann      |
|  MUSA_VISIBLE_DEVICES   | quay.io/ramalama/musa      |

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

#### **--model**=*model*
AI Model to serve as the agent backend (default: hf://Qwen/Qwen3-1.7B-GGUF/Qwen3-1.7B-Q8_0.gguf)

#### **--model-draft**

A draft model is a smaller, faster model that helps accelerate the decoding
process of larger, more complex models, like Large Language Models (LLMs). It
works by generating candidate sequences of tokens that the larger model then
verifies and refines. This approach, often referred to as speculative decoding,
can significantly improve the speed of inferencing by reducing the number of
times the larger model needs to be invoked.

Use --runtime-arg to pass the other draft model related parameters.
Make sure the sampling parameters like top_k on the web UI are set correctly.

#### **--name**, **-n**
Name of the container to run the Model in.

#### **--network**=*""*
set the network mode for the container

#### **--ngl**
number of gpu layers, 0 means CPU inferencing, 999 means use max layers (default: -1)
The default -1, means use whatever is automatically deemed appropriate (0 or 999)

#### **--oci-runtime**

Override the default OCI runtime used to launch the container. Container
engines like Podman and Docker, have their own default oci runtime that they
use. Using this option RamaLama will override these defaults.

On Nvidia based GPU systems, RamaLama defaults to using the
`nvidia-container-runtime`. Use this option to override this selection.

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
Specify seed rather than using random seed model interaction

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
Maximum number of cpu threads to use.
The default is to use half the cores available on this system for the number of threads.

#### **--tls-verify**=*true*
require HTTPS and verify certificates when contacting OCI registries

#### **--webui**=*on* | *off*
Enable or disable the web UI for the served model (enabled by default). When set to "on" (the default), the web interface is properly initialized. When set to "off", the `--no-webui` option is passed to the llama-server command to disable the web interface.

#### **--workdir**, **-w**
Local directory to mount into the agent container at /work. Also sets /work as the working directory.

## EXAMPLES

Run the agent with default settings:
```
ramalama agent
```

Run the agent with a custom model:
```
ramalama agent --model gpt-oss
```

Run the agent with a custom agent image:
```
ramalama agent --agent-image ghcr.io/block/goose:1.27.0
```

Turn off thinking mode in the model the agent is connecting to (may result in faster responses):
```
ramalama agent --thinking=off
```

Start an interactive session with access to a local directory:
```
ramalama agent -w ./src
```

Request the agent to perform actions non-interactively:
```
ramalama agent -w ./src Please analyze the source code in the current directory
```

Send instructions to the agent via stdin:
```
echo "What is the speed of light in meters per second?" | ramalama agent
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-run(1)](ramalama-run.1.md)**, **[ramalama-serve(1)](ramalama-serve.1.md)**

## HISTORY
Mar 2026, Originally compiled by Mike Bonnet <mikeb@redhat.com>
