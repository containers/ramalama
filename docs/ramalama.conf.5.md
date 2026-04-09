---
title: Configuration File
sidebar_label: ramalama.conf
description: Configuration file documentation for RamaLama AI tool
keywords: [ramalama, configuration, config, ramalama.conf, TOML]
---

# Configuration File

## Overview

The `ramalama.conf` file specifies default configuration options and command-line flags for RamaLama. RamaLama reads all configuration files if they exist and uses them to modify the default behavior when running AI models on the host system.

The configuration file uses the [TOML format](https://toml.io), which is easy to modify, version, and understand.

## File Locations

RamaLama searches for configuration files in multiple locations. Files processed later override settings from earlier ones.

### Global Configuration Files

These configuration files affect all users on the system:

| Path | Exception |
|------|----------|
| `/usr/share/ramalama/ramalama.conf` | Linux |
| `/usr/local/share/ramalama/ramalama.conf` | Linux |
| `/etc/ramalama/ramalama.conf` | Linux |
| `/etc/ramalama/ramalama.conf.d/*.conf` | Linux |
| `$HOME/.local/.pipx/venvs/usr/share/ramalama/ramalama.conf` | macOS (pipx installation) |

### User Configuration Files

These configuration files are specific to individual users:

| Path | Notes |
|------|-------|
| `$XDG_CONFIG_HOME/ramalama/ramalama.conf` | Primary user config |
| `$XDG_CONFIG_HOME/ramalama/ramalama.conf.d/*.conf` | User config drop-in files |
| `$HOME/.config/ramalama/ramalama.conf` | Fallback if `$XDG_CONFIG_HOME` not set |
| `$HOME/.config/ramalama/ramalama.conf.d/*.conf` | Fallback drop-in files |

:::note Configuration Priority
Fields specified in later configuration files override options from earlier files. Configuration files in `.d` directories are processed in alphanumeric sorted order and must end with `.conf`.
:::

## Environment Variables

### RAMALAMA_CONFIG

If the `RAMALAMA_CONFIG` environment variable is set, all system and user configuration files are ignored, and only the specified configuration file is loaded.

**Example:**
```bash
export RAMALAMA_CONFIG=/path/to/custom/ramalama.conf
ramalama run tiny
```

## Configuration Format

As mentioned above, the configuration file uses the [TOML format](https://toml.io). Every option is nested under its table, with no bare options allowed.

**Basic TOML structure:**

```toml
[table_name]
option = "value"

[table_name.subtable]
option = "value"
```

**Example configuration:**

```toml
[ramalama]
backend = "auto"
engine = "podman"
store = "$HOME/.local/share/ramalama"

[ramalama.images]
CUDA_VISIBLE_DEVICES = "quay.io/ramalama/cuda"
```

## Configuration Reference

### ramalama table

The `ramalama` table contains settings to configure and manage the container runtime and AI model behavior.

`[[ramalama]]`

---

#### api

**api**="none"

**Type:** string  
**Default:** `"none"`

Unified API layer for Inference, RAG, Agents, Tools, Safety, Evals, and Telemetry.

**Valid options:**
- `llama-stack`
- `none`

**Example:**
```toml
[ramalama]
api = "llama-stack"
```

---

#### api_key

**api_key**=""

**Type:** string  
**Default:** `""`  
**Environment Override:** `RAMALAMA_API_KEY`

OpenAI-compatible API key for hosted provider authentication.

**Example:**
```toml
[ramalama]
api_key = "your-api-key-here"
```

---

#### backend

**backend**="auto"

**Type:** string  
**Default:** `"auto"`  
**Environment Override:** `RAMALAMA_BACKEND`

Specifies the GPU backend to use for inference. This setting affects which container image is selected and how GPU resources are utilized.

**Valid options:**

- **`auto`** (default): Automatically selects the preferred backend based on detected GPU:
  - AMD GPUs: `vulkan` (Linux/macOS) or `rocm` (Windows)
  - NVIDIA GPUs: `cuda`
  - Intel GPUs: `vulkan` (Linux/macOS) or `sycl` (Windows); `openvino` available as explicit option
  - No GPU: `vulkan` (CPU fallback)

- **`vulkan`**: Vulkan-based inference (compatible with AMD, Intel, and CPU)
- **`rocm`**: AMD ROCm backend (AMD GPUs only)
- **`cuda`**: NVIDIA CUDA backend (NVIDIA GPUs only)
- **`sycl`**: Intel SYCL/oneAPI backend (Intel GPUs only)
- **`openvino`**: Intel OpenVINO backend (Intel GPUs only); uses `ghcr.io/ggml-org/llama.cpp:full-openvino`

:::warning Platform-Specific Behavior
On Windows (including WSL2), Vulkan support is limited and depends on system configuration. In such cases, vendor-specific backends (`rocm` for AMD, `sycl` for Intel) may be preferred when using `backend="auto"`.
:::

**Example:**
```toml
[ramalama]
backend = "vulkan"
```

---

#### carimage


**carimage**="registry.access.redhat.com/ubi10-micro:latest"

**Type:** string  
**Default:** `"registry.access.redhat.com/ubi10-micro:latest"`

OCI model `carimage` used when building and pushing models with `--type=car`.

**Example:**
```toml
[ramalama]
carimage = "registry.access.redhat.com/ubi10-micro:latest"
```

---

#### container

**container**=true

**Type:** boolean  
**Default:** `true`  
**Environment Override:** `RAMALAMA_IN_CONTAINER`

Run RamaLama in the default container.

**Example:**
```toml
[ramalama]
container = true
```

---

#### convert_type

**convert_type**="raw"

**Type:** string  
**Default:** `"raw"`

Convert the AI model to the specified OCI object type.

**Valid options:**

| Type | Description |
|------|-------------|
| `artifact` | Store AI models as artifacts |
| `car` | Traditional OCI image including base image with the model stored in a `/models` subdirectory |
| `raw` | Traditional OCI image including only the model and a link file `model.file` pointed at it stored at `/` |

**Example:**
```toml
[ramalama]
convert_type = "artifact"
```

---

#### ctx_size

**ctx_size**=0

**Type:** integer  
**Default:** `0`

Size of the prompt context. When set to `0`, the context size is loaded from the model.

**Example:**
```toml
[ramalama]
ctx_size = 4096
```

---

#### engine

**engine**="podman"

**Type:** string  
**Default:** `"podman"`  
**Environment Override:** `RAMALAMA_CONTAINER_ENGINE`

Run RamaLama using the specified container engine.

**Valid options:**
- `podman`
- `docker`

**Example:**
```toml
[ramalama]
engine = "podman"
```

---

#### env

**env**=[]

**Type:** array  
**Default:** `[]`

Environment variables to be added when running within a container engine (Podman or Docker).

**Example:**
```toml
[ramalama]
env = ["LLAMA_ARG_THREADS=10", "CUSTOM_VAR=value"]
```

---

#### gguf_quantization_mode

**gguf_quantization_mode**="Q4_K_M"

**Type:** string  
**Default:** `"Q4_K_M"`

The quantization mode used when creating OCI-formatted AI models.

**Available options:**
- `Q2_K`
- `Q3_K_S`, `Q3_K_M`, `Q3_K_L`
- `Q4_0`, `Q4_K_S`, `Q4_K_M`
- `Q5_0`, `Q5_K_S`, `Q5_K_M`
- `Q6_K`
- `Q8_0`

**Example:**
```toml
[ramalama]
gguf_quantization_mode = "Q4_K_M"
```

---

#### host

**host**="0.0.0.0"

**Type:** string  
**Default:** `"0.0.0.0"`

IP address for llama.cpp to listen on when serving models.

**Example:**
```toml
[ramalama]
host = "127.0.0.1"
```

---

#### image

**image**="quay.io/ramalama/ramalama:latest"

**Type:** string  
**Default:** `"quay.io/ramalama/ramalama:latest"`  
**Environment Override:** `RAMALAMA_IMAGE`

OCI container image to run with the specified AI model.

**Example:**
```toml
[ramalama]
image = "quay.io/ramalama/ramalama:latest"
```

---

#### images

**images**=Built-in runtime defaults

**Type:** table  
**Default:** Built-in runtime defaults

User-override entries for runtime-specific container images. Each runtime plugin defines its own built-in defaults; entries here override those defaults.

**For llama.cpp runtime**, set GPU environment variable names to override the image for that accelerator:

```toml
[[ramalama.images]]
HIP_VISIBLE_DEVICES = "quay.io/ramalama/rocm"
CUDA_VISIBLE_DEVICES = "quay.io/ramalama/cuda"
ASAHI_VISIBLE_DEVICES = "quay.io/ramalama/asahi"
INTEL_VISIBLE_DEVICES = "quay.io/ramalama/intel-gpu"
ASCEND_VISIBLE_DEVICES = "quay.io/ramalama/cann"
MUSA_VISIBLE_DEVICES = "quay.io/ramalama/musa"
```

**For vllm runtime**, use `VLLM` to override the image regardless of GPU, or `VLLM_<GPU_ENV_VAR>` to override for a specific accelerator:

```toml
[[ramalama.images]]
VLLM = "registry.redhat.io/rhelai1/ramalama-vllm"
VLLM_CUDA_VISIBLE_DEVICES = "docker.io/vllm/vllm-openai"
```

---

#### keep_groups

**keep_groups**=false

**Type:** boolean  
**Default:** `false`

Pass `--group-add keep-groups` to Podman when using Podman. In some cases, this is needed to access the GPU from a rootless container.

**Example:**
```toml
[ramalama]
keep_groups = true
```

---

#### log_level

**log_level**="warning"

**Type:** string  
**Default:** `"warning"`

Set the logging level of the RamaLama application.

**Valid values:**
- `debug`
- `info`
- `warning`
- `error`
- `critical`

:::note
The `--debug` command-line option overrides this field and forces the system to use debug level.
:::

**Example:**
```toml
[ramalama]
log_level = "info"
```

---

#### max_tokens

**max_tokens**=0

**Type:** integer  
**Default:** `0`

Maximum number of tokens to generate. Set to `0` for unlimited output.

This parameter is mapped to the appropriate runtime-specific parameter when executing models.

**Example:**
```toml
[ramalama]
max_tokens = 2048
```

---

#### prefix

**prefix**=Based on container engine

**Type:** string  
**Default:** Based on container engine

Specify the default prefix for chat and run commands. By default, the prefix depends on the container engine used.

**Default prefixes:**

| Container Engine | Prefix |
|------------------|--------|
| Podman | `"🦭 > "` |
| Docker | `"🐋 > "` |
| No Engine | `"🦙 > "` |
| No EMOJI support | `"> "` |

**Example:**
```toml
[ramalama]
prefix = "AI> "
```

---

#### port

**port**="8080"

**Type:** integer
**Default:** `"8080"`

Specify the initial port for a range of 101 ports for services to listen on. If this port is unavailable, another free port from this range will be selected.

**Example:**
```toml
[ramalama]
port = "8081"
```

---

#### pull

**pull**="newer"

**Type:** string  
**Default:** `"newer"`

Policy for pulling container images from registries.

**Valid options:**

- **`always`**: Always pull the image and throw an error if the pull fails.
- **`missing`**: Only pull the image when it does not exist in local container storage. Throw an error if no image is found and the pull fails.
- **`never`**: Never pull the image but use the one from local container storage. Throw an error when no image is found.
- **`newer`**: Pull if the image on the registry is newer than the one in local container storage. An image is considered newer when the digests are different. Pull errors are suppressed if a local image was found.

**Example:**
```toml
[ramalama]
pull = "missing"
```

---

#### rag_format

**rag_format**="qdrant"

**Type:** string  
**Default:** `"qdrant"`

Specify the default output format for the `ramalama rag` command.

**Valid options:**
- `qdrant`
- `json`
- `markdown`
- `milvus`

**Example:**
```toml
[ramalama]
rag_format = "json"
```

---

#### rag_image

**Type:** string  
**Default:** `"quay.io/ramalama/ramalama-rag"`

OCI container image to run with the specified AI model when using RAG content.

**Example:**
```toml
[ramalama]
rag_image = "quay.io/ramalama/ramalama-rag"
```

---

#### rag_images

**rag_images**=Built-in GPU defaults

**Type:** table
**Default:** Built-in GPU defaults

User-override entries for GPU-specific RAG container images. Built-in GPU defaults (CUDA, ROCm, Intel) are defined internally; entries here override those defaults.

**Example:**
```toml
[ramalama.rag_images]
CUDA_VISIBLE_DEVICES = "quay.io/ramalama/cuda-rag"
HIP_VISIBLE_DEVICES = "quay.io/ramalama/rocm-rag"
INTEL_VISIBLE_DEVICES = "quay.io/ramalama/intel-gpu-rag"
```

---

#### runtime

**runtime**="llama.cpp"

**Type:** string  
**Default:** `"llama.cpp"`

Specify the AI runtime to use.

**Valid options:**
- `llama.cpp`
- `vllm`
- `mlx`

**Example:**
```toml
[ramalama]
runtime = "vllm"
```

---

#### selinux

**selinux**=false

**Type:** boolean  
**Default:** `false`

Enable SELinux container separation enforcement.

**Example:**
```toml
[ramalama]
selinux = true
```

---

#### store

**store**="$HOME/.local/share/ramalama"

**Type:** string  
**Default:** `"$HOME/.local/share/ramalama"`

Store AI models in the specified directory.

**Example:**
```toml
[ramalama]
store = "/custom/path/to/models"
```

---

#### summarize_after

**summarize_after**=4

**Type:** integer  
**Default:** `4`

Automatically summarize conversation history after N messages to prevent context growth.

When enabled, RamaLama will periodically condense older messages into a summary, keeping only recent messages and the summary. This prevents the context from growing indefinitely during long chat sessions.

Set to `0` to disable.

**Example:**
```toml
[ramalama]
summarize_after = 10
```

---

#### temp

**temp**="0.8"

**Type:** float 
**Default:** `"0.8"`

Temperature of the response from the AI model.

According to llama.cpp:
- Lower numbers produce more deterministic responses
- Higher numbers produce more creative responses but may hallucinate when set too high

**Usage guidance:**
- Lower values (0.1-0.5): Good for virtual assistants requiring deterministic responses
- Higher values (0.7-1.2): Good for roleplay or creative tasks like editing stories

**Example:**
```toml
[ramalama]
temp = "0.7"
```

---

#### transport

**transport**="ollama"

**Type:** string  
**Default:** `"ollama"`  
**Environment Override:** `RAMALAMA_TRANSPORT`

Specify the default transport to be used for pulling and pushing AI models.

**Valid options:**
- `oci`
- `ollama`
- `huggingface`

**Example:**
```toml
[ramalama]
transport = "huggingface"
```

---

### ramalama.http_client table

HTTP client configuration settings.

`[[ramalama.http_client]]`

#### max_retries

**max_retries**=5

**Type:** integer  
**Default:** `5`

The maximum number of times to retry a failed download.

**Example:**
```toml
[ramalama.http_client]
max_retries = 10
```

---

#### max_retry_delay

**max_retry_delay**=30

**Type:** integer  
**Default:** `30`

The maximum delay between retry attempts in seconds.

**Example:**
```toml
[ramalama.http_client]
max_retry_delay = 60
```

---

### ramalama.provider table

The `ramalama.provider` table configures hosted API providers that RamaLama can proxy to.

`[[ramalama.provider]]`

#### openai

**openai**=""

**Type:** table  
**Default:** `""`

Configuration settings for the OpenAI hosted provider.

**Example:**
```toml
[[ramalama.provider]]
openai = ""
```

---

#### openai.api_key

**api_key**=""

**Type:** string  
**Default:** `""`

Provider-specific API key used when invoking OpenAI-hosted transports. Overrides `RAMALAMA_API_KEY` when set.

**Example:**
```toml
[[ramalama.provider.openai]]
api_key = "your-openai-api-key"
```

---

### ramalama.benchmarks table

The `ramalama.benchmarks` table contains benchmark-related settings.

`[[ramalama.benchmarks]]`

#### storage_folder


**storage_folder**="<default store>/benchmarks"

**Type:** string  
**Default:** `"\<default store>/benchmarks"`

Manually specify where to save benchmark results.

By default, results are stored in the default model store directory under `benchmarks/`. Changing `ramalama.store` does not automatically update this path; set `ramalama.benchmarks.storage_folder` explicitly if needed.

**Example:**
```toml
[ramalama.benchmarks]
storage_folder = "/custom/benchmark/results"
```

---

### ramalama.user table

The `ramalama.user` table contains user preference settings.

`[[ramalama.user]]`

#### no_missing_gpu_prompt

**no_missing_gpu_prompt**=false

**Type:** boolean  
**Default:** `false`  
**Environment Override:** `RAMALAMA_USER__NO_MISSING_GPU_PROMPT`

Suppress the interactive prompt when running on macOS with a Podman VM that does not support GPU acceleration (e.g., applehv provider).

When set to `true`, RamaLama will automatically proceed without GPU support instead of prompting the user for confirmation. This is useful for automation and scripting scenarios where interactive prompts are not desired.

**Example:**
```toml
[ramalama.user]
no_missing_gpu_prompt = true
```

---

## Complete Configuration Example

Here is a complete example configuration file demonstrating various settings:

```toml
[ramalama]
backend = "cuda"
container = true
engine = "podman"
store = "$HOME/.local/share/ramalama"
log_level = "info"
temp = "0.8"
max_tokens = 2048
transport = "huggingface"
runtime = "llama.cpp"
port = "8080"
pull = "newer"

[ramalama.images]
CUDA_VISIBLE_DEVICES = "quay.io/ramalama/cuda"
HIP_VISIBLE_DEVICES = "quay.io/ramalama/rocm"

[ramalama.http_client]
max_retries = 5
max_retry_delay = 30

[ramalama.provider.openai]
api_key = "your-api-key-here"

[ramalama.benchmarks]
storage_folder = "$HOME/.local/share/ramalama/benchmarks"

[ramalama.user]
no_missing_gpu_prompt = false
```
