% ramalama-serve 1

## NAME
ramalama\-serve - serve REST API on specified AI Model

## SYNOPSIS
**ramalama serve** [*options*] [_model_ ...]

## DESCRIPTION
Serve specified AI Model as a chat bot. RamaLama pulls specified AI Model from
registry if it does not exist in local storage.

When invoked with two or more model arguments, or without any model argument,
starts in **router mode**: models are mounted into a container and served via
llama.cpp's multi-model directory feature. Requests are routed to the
appropriate model based on the model name in the API request. Router mode
requires a container runtime.

With no model arguments, all locally stored GGUF models are served. With
multiple model arguments, only the specified models are served.


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

## REST API ENDPOINTS
Under the hood, `ramalama-serve` uses the `llama.cpp` HTTP server by default. When using `--runtime=vllm`, it uses the vLLM server. When using `--runtime=mlx`, it uses the MLX LM server.

For REST API endpoint documentation, see:
- llama.cpp: [https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md#api-endpoints](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md#api-endpoints)
- vLLM: [https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html)
- MLX LM: [https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/SERVER.md](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/SERVER.md)

## OPTIONS

#### **--add-to-unit**

format: --add-to-unit section:key:value

Adds to the generated unit file (quadlet) in the section *section* the key *key* with the value *value*.

Useful, for instance, to add environment variables to the generated unit file, or to place the container in a specific pod/network (Container:Network:xxx.network).

**Only valid with *--generate* parameter.**

Section, key and value are required and must be separated by colons.


[//]: # (BEGIN included file options/api.md)
#### **--api**=**llama-stack** | none**
Unified API layer for Inference, RAG, Agents, Tools, Safety, Evals, and Telemetry.(default: none)
The default can be overridden in the `ramalama.conf` file.

[//]: # (END   included file options/api.md)


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
ramalama serve granite

# Force Vulkan backend
ramalama serve --backend vulkan granite

# Force ROCm backend on AMD GPU
ramalama serve --backend rocm granite
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

#### **--detach**, **-d**
Run the container in the background and print the new container ID.
The default is TRUE. The --nocontainer option forces this option to False.

Use the `ramalama stop` command to stop the container running the served ramalama Model.


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

#### **--dri**=*on* | *off*
Enable or disable mounting `/dev/dri` into the container when running with `--api=llama-stack` (enabled by default). Use to prevent access to the host device when not required, or avoid errors in environments where `/dev/dri` is not available.


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

#### **--generate**=type
Generate specified configuration format for running the AI Model as a service

| Key          | Description                                                              |
| ------------ | -------------------------------------------------------------------------|
| quadlet      | Podman supported container definition for running AI Model under systemd |
| kube         | Kubernetes YAML definition for running the AI Model as a service         |
| quadlet/kube | Kubernetes YAML definition for running the AI Model as a service and Podman supported container definition for running the Kube YAML specified pod under systemd|
| compose      | Compose YAML definition for running the AI Model as a service            |

Optionally, an output directory for the generated files can be specified by
appending the path to the type, e.g. `--generate kube:/etc/containers/systemd`.



[//]: # (BEGIN included file options/help.md)
#### **--help**, **-h**
Show this help message and exit

[//]: # (END   included file options/help.md)


[//]: # (BEGIN included file options/host.md)
#### **--host**="127.0.0.1"
IP address for the model server to listen on. Defaults to "127.0.0.1", so the
served model is only reachable from the local machine. To expose it on the
network, set this to a wildcard address such as "0.0.0.0" (IPv4) or "::"
(dual-stack).

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
ramalama serve --image ghcr.io/ggml-org/llama.cpp:full-vulkan MODEL
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


[//]: # (BEGIN included file options/pull.md)
#### **--pull**=*policy*
Pull image policy. The default is **missing**.

- **always**: Always pull the image and throw an error if the pull fails.
- **missing**: Only pull the image when it does not exist in the local containers storage. Throw an error if no image is found and the pull fails.
- **never**: Never pull the image but use the one from the local containers storage. Throw an error when no image is found.
- **newer**: Pull if the image on the registry is newer than the one in the local containers storage. An image is considered to be newer when the digests are different. Comparing the time stamps is prone to errors. Pull errors are suppressed if a local image was found.

[//]: # (END   included file options/pull.md)


[//]: # (BEGIN included file options/rag-pair.md)
#### **--rag**=
Specify path to Retrieval-Augmented Generation (RAG) database or an OCI Image containing a RAG database

Note: RAG support requires AI Models be run within containers, --nocontainer not supported. Docker does not support image mounting, meaning Podman support required.

#### **--rag-image**=
The image to use to process the RAG database specified by the `--rag` option. The image must contain the `/usr/bin/rag_framework` executable, which
will create a proxy which embellishes client requests with RAG data before passing them on to the LLM, and returns the responses.

[//]: # (END   included file options/rag-pair.md)


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


[//]: # (BEGIN included file options/stack-image.md)
#### **--stack-image**=
The image to use to start the [Open-source agentic API server (ogx)](https://ogx-ai.github.io/). It is used when `--api llama-stack` is used. The image will get following environment variables: RAMALAMA_URL the url where the model server is running, INFERENCE_MODEL the model of the model server and RAMALAMA_RUNTIME the runtime used by the model server. The API server must run on port 8321.

[//]: # (END   included file options/stack-image.md)


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


[//]: # (BEGIN included file options/webui.md)
#### **--webui**=*on* | *off*
Enable or disable the web UI for the served model (enabled by default). When set to "on" (the default), the web interface is properly initialized. When set to "off", the `--no-webui` option is passed to the llama-server command to disable the web interface.

[//]: # (END   included file options/webui.md)

## EXAMPLES

[//]: # (BEGIN included file options/serve-examples-body.md)
### Run two AI Models at the same time. Notice both are running within Podman Containers.
```

$ ramalama serve -d -p 8080 --name mymodel ollama://smollm:135m
09b0e0d26ed28a8418fb5cd0da641376a08c435063317e89cf8f5336baf35cfa

$ ramalama serve -d -n example --port 8081 oci://quay.io/mmortari/gguf-py-example/v1/example.gguf
3f64927f11a5da5ded7048b226fbe1362ee399021f5e8058c73949a677b6ac9c

$ podman ps
CONTAINER ID  IMAGE                             COMMAND               CREATED         STATUS         PORTS                   NAMES
09b0e0d26ed2  quay.io/ramalama/ramalama:latest  /usr/bin/ramalama...  32 seconds ago  Up 32 seconds  0.0.0.0:8080->8080/tcp  ramalama_sTLNkijNNP
3f64927f11a5  quay.io/ramalama/ramalama:latest  /usr/bin/ramalama...  17 seconds ago  Up 17 seconds  0.0.0.0:8081->8081/tcp  ramalama_YMPQvJxN97
```

### Generate quadlet service off of HuggingFace granite Model
```
$ ramalama serve --name MyGraniteServer --generate=quadlet granite
Generating quadlet file: MyGraniteServer.container

$ cat MyGraniteServer.container
[Unit]
Description=RamaLama $HOME/.local/share/ramalama/models/huggingface/instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf AI Model Service
After=local-fs.target

[Container]
AddDevice=-/dev/accel
AddDevice=-/dev/dri
AddDevice=-/dev/kfd
Exec=llama-server --port 1234 -m $HOME/.local/share/ramalama/models/huggingface/instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf
Image=quay.io/ramalama/ramalama:latest
Mount=type=bind,src=/home/dwalsh/.local/share/ramalama/models/huggingface/instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf,target=/mnt/models/model.file,ro,Z
ContainerName=MyGraniteServer
PublishPort=8080

[Install]
# Start by default on boot
WantedBy=multi-user.target default.target

$ mv MyGraniteServer.container $HOME/.config/containers/systemd/
$ systemctl --user daemon-reload
$ systemctl start --user MyGraniteServer
$ systemctl status --user MyGraniteServer
● MyGraniteServer.service - RamaLama granite AI Model Service
     Loaded: loaded (/home/dwalsh/.config/containers/systemd/MyGraniteServer.container; generated)
    Drop-In: /usr/lib/systemd/user/service.d
	    └─10-timeout-abort.conf
     Active: active (running) since Fri 2024-09-27 06:54:17 EDT; 3min 3s ago
   Main PID: 3706287 (conmon)
      Tasks: 20 (limit: 76808)
     Memory: 1.0G (peak: 1.0G)

...
$ podman ps
CONTAINER ID  IMAGE                             COMMAND               CREATED        STATUS        PORTS                    NAMES
7bb35b97a0fe  quay.io/ramalama/ramalama:latest  llama-server --po...  3 minutes ago  Up 3 minutes  0.0.0.0:43869->8080/tcp  MyGraniteServer
```

### Generate quadlet service off of tiny OCI Model
```
$ ramalama --runtime=vllm serve --name tiny --generate=quadlet oci://quay.io/rhatdan/tiny:latest
Downloading quay.io/rhatdan/tiny:latest...
Trying to pull quay.io/rhatdan/tiny:latest...
Getting image source signatures
Copying blob 65ba8d40e14a skipped: already exists
Copying blob e942a1bf9187 skipped: already exists
Copying config d8e0b28ee6 done   |
Writing manifest to image destination
Generating quadlet file: tiny.container
Generating quadlet file: tiny.image
Generating quadlet file: tiny.volume

$ cat tiny.container
[Unit]
Description=RamaLama /run/model/model.file AI Model Service
After=local-fs.target

[Container]
AddDevice=-/dev/accel
AddDevice=-/dev/dri
AddDevice=-/dev/kfd
Exec=vllm serve --port 8080 /run/model/model.file
Image=quay.io/ramalama/ramalama:latest
Mount=type=volume,source=tiny:latest.volume,dest=/mnt/models,ro
ContainerName=tiny
PublishPort=8080

[Install]
# Start by default on boot
WantedBy=multi-user.target default.target

$ cat tiny.volume
[Volume]
Driver=image
Image=tiny:latest.image

$ cat tiny.image
[Image]
Image=quay.io/rhatdan/tiny:latest
```

### Generate quadlet service off of tiny OCI Model and output to directory
```
$ ramalama --runtime=vllm serve --name tiny --generate=quadlet:~/.config/containers/systemd/ oci://quay.io/rhatdan/tiny:latest
Generating quadlet file: tiny.container
Generating quadlet file: tiny.image
Generating quadlet file: tiny.volume

$ ls ~/.config/containers/systemd/
tiny.container tiny.image tiny.volume
```

### Generate a Kubernetes YAML file named MyTinyModel
```
$ ramalama serve --name MyTinyModel --generate=kube oci://quay.io/rhatdan/tiny-car:latest
Generating Kubernetes YAML file: MyTinyModel.yaml
$ cat MyTinyModel.yaml
# Save the output of this file and use kubectl create -f to import
# it into Kubernetes.
#
# Created with ramalama-0.0.21
apiVersion: apps/v1
kind: Deployment
metadata:
  name: MyTinyModel
  labels:
    app: MyTinyModel
spec:
  replicas: 1
  selector:
    matchLabels:
      app: MyTinyModel
  template:
    metadata:
      labels:
	app: MyTinyModel
    spec:
      containers:
      - name: MyTinyModel
	image: quay.io/ramalama/ramalama:latest
	command: ["llama-server"]
	args: ['--port', '8080', '-m', '/mnt/models/model.file']
	ports:
	- containerPort: 8080
	volumeMounts:
	- mountPath: /mnt/models
	  subPath: /models
	  name: model
	- mountPath: /dev/dri
	  name: dri
      volumes:
      - image:
	  reference: quay.io/rhatdan/tiny-car:latest
	  pullPolicy: IfNotPresent
	name: model
      - hostPath:
	  path: /dev/dri
	name: dri
```

### Generate Compose file
```
$ ramalama serve --name=my-smollm-server --port 1234 --generate=compose smollm:135m
Generating Compose YAML file: docker-compose.yaml
$ cat docker-compose.yaml
version: '3.8'
services:
  my-smollm-server:
    image: quay.io/ramalama/ramalama:latest
    container_name: my-smollm-server
    command: ramalama serve --host 0.0.0.0 --port 1234 smollm:135m
    ports:
      - "1234:1234"
    volumes:
      - ~/.local/share/ramalama/models/smollm-135m-instruct:/mnt/models/model.file:ro
    environment:
      - HOME=/tmp
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges
      - label=disable
```

### Generate a Llama Stack Kubernetes YAML file named MyLlamaStack
```
$ ramalama serve --api llama-stack --name MyLlamaStack --generate=kube oci://quay.io/rhatdan/granite:latest
Generating Kubernetes YAML file: MyLlamaStack.yaml
$ cat MyLlamaStack.yaml
apiVersion: v1
kind: Deployment
metadata:
  name: MyLlamaStack
  labels:
    app: MyLlamaStack
spec:
  replicas: 1
  selector:
    matchLabels:
      app: MyLlamaStack
  template:
    metadata:
      labels:
	ai.ramalama: ""
	app: MyLlamaStack
	ai.ramalama.model: oci://quay.io/rhatdan/granite:latest
	ai.ramalama.engine: podman
	ai.ramalama.runtime: llama.cpp
	ai.ramalama.port: 8080
	ai.ramalama.command: serve
    spec:
      containers:
      - name: model-server
	image: quay.io/ramalama/ramalama:0.8
	command: ["llama-server"]
	args: ['--port', '8081', '--model', '/mnt/models/model.file', '--alias', 'quay.io/rhatdan/granite:latest', '--temp', '0.8', '--jinja', '-v', '--threads', 16, '--host', '127.0.0.1']
	securityContext:
	  allowPrivilegeEscalation: false
	  capabilities:
	    drop:
	    - CAP_CHOWN
	    - CAP_FOWNER
	    - CAP_FSETID
	    - CAP_KILL
	    - CAP_NET_BIND_SERVICE
	    - CAP_SETFCAP
	    - CAP_SETGID
	    - CAP_SETPCAP
	    - CAP_SETUID
	    - CAP_SYS_CHROOT
	    add:
	    - CAP_DAC_OVERRIDE
	  seLinuxOptions:
	    type: spc_t
	volumeMounts:
	- mountPath: /mnt/models
	  subPath: /models
	  name: model
	- mountPath: /dev/dri
	  name: dri
      - name: llama-stack
	image: quay.io/ramalama/llama-stack:0.8
	args:
	- /bin/sh
	- -c
	- llama stack run --image-type venv /etc/ramalama/ramalama-run.yaml
	env:
	- name: RAMALAMA_URL
	  value: http://127.0.0.1:8081
	- name: INFERENCE_MODEL
	  value: quay.io/rhatdan/granite:latest
	securityContext:
	  allowPrivilegeEscalation: false
	  capabilities:
	    drop:
	    - CAP_CHOWN
	    - CAP_FOWNER
	    - CAP_FSETID
	    - CAP_KILL
	    - CAP_NET_BIND_SERVICE
	    - CAP_SETFCAP
	    - CAP_SETGID
	    - CAP_SETPCAP
	    - CAP_SETUID
	    - CAP_SYS_CHROOT
	    add:
	    - CAP_DAC_OVERRIDE
	  seLinuxOptions:
	    type: spc_t
	ports:
	- containerPort: 8321
	  hostPort: 8080
      volumes:
      - hostPath:
	  path: quay.io/rhatdan/granite:latest
	name: model
      - hostPath:
	  path: /dev/dri
	name: dri
```

### Generate a Kubernetes YAML file named MyTinyModel shown above, but also generate a quadlet to run it in.
```
$ ramalama --name MyTinyModel --generate=quadlet/kube oci://quay.io/rhatdan/tiny-car:latest
run_cmd:  podman image inspect quay.io/rhatdan/tiny-car:latest
Generating Kubernetes YAML file: MyTinyModel.yaml
Generating quadlet file: MyTinyModel.kube
$ cat MyTinyModel.kube
[Unit]
Description=RamaLama quay.io/rhatdan/tiny-car:latest Kubernetes YAML - AI Model Service
After=local-fs.target

[Kube]
Yaml=MyTinyModel.yaml

[Install]
# Start by default on boot
WantedBy=multi-user.target default.target
```

[//]: # (END   included file options/serve-examples-body.md)

## NVIDIA CUDA Support

See **[ramalama-cuda(7)](ramalama-cuda.7.md)** for setting up the host Linux system for CUDA support.

## MLX Support

The MLX runtime is designed for Apple Silicon Macs and provides optimized performance on these systems. MLX support has the following requirements:

- **Operating System**: macOS only
- **Hardware**: Apple Silicon (M1, M2, M3, or later)
- **Container Mode**: MLX requires `--nocontainer` as it cannot run inside containers
- **Dependencies**: The `mlx-lm` uv package installed on the host system as a uv tool

To install MLX dependencies, use `uv`:
```bash
uv tool install mlx-lm
# or upgrade to the latest version:
uv tool upgrade mlx-lm
```

Example usage:
```bash
ramalama --runtime=mlx serve hf://mlx-community/Unsloth-Phi-4-4bit
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-stop(1)](ramalama-stop.1.md)**, **quadlet(1)**, **systemctl(1)**, **podman(1)**, **podman-ps(1)**, **[ramalama-cuda(7)](ramalama-cuda.7.md)**, **[ramalama.conf(5)](ramalama.conf.5.md)**

## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
