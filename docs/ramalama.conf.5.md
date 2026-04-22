% ramalama.conf 5 RamaLama AI tool configuration file

# NAME
ramalama.conf - configuration files that define default RamaLama options and CLI flag values.

# DESCRIPTION
Use `ramalama.conf` to set defaults for RamaLama commands.
RamaLama reads config files in order and merges values, where later files override earlier ones.

RamaLama reads the following global configuration paths:

| Path | Notes |
| --- | --- |
| `/usr/share/ramalama/ramalama.conf` | Linux |
| `/usr/local/share/ramalama/ramalama.conf` | Linux |
| `/etc/ramalama/ramalama.conf` | Linux |
| `/etc/ramalama/ramalama.conf.d/*.conf` | Linux |
| `$HOME/.local/pipx/venvs/ramalama/share/ramalama/ramalama.conf` | pipx install |

RamaLama reads the following user configuration paths:

| Path | Notes |
| --- | --- |
| `$XDG_DATA_HOME/ramalama/ramalama.conf` | Preferred data path |
| `$XDG_DATA_HOME/ramalama/ramalama.conf.d/*.conf` | Additional data snippets |
| `$HOME/.local/share/ramalama/ramalama.conf` | Used when `$XDG_DATA_HOME` is unset |
| `$HOME/.local/share/ramalama/ramalama.conf.d/*.conf` | Used when `$XDG_DATA_HOME` is unset |
| `$XDG_CONFIG_HOME/ramalama/ramalama.conf` | Preferred user path |
| `$XDG_CONFIG_HOME/ramalama/ramalama.conf.d/*.conf` | Additional user snippets |
| `$HOME/.config/ramalama/ramalama.conf` | Used when `$XDG_CONFIG_HOME` is unset |
| `$HOME/.config/ramalama/ramalama.conf.d/*.conf` | Used when `$XDG_CONFIG_HOME` is unset |

Notes:
- Files in `.d` directories are loaded in alphanumeric order.
- Files in `.d` directories must end with `.conf`.

## ENVIRONMENT VARIABLES
If `RAMALAMA_CONFIG` is set, RamaLama ignores all default system/user config paths and loads only the specified file.

# FORMAT
RamaLama uses TOML.
Every setting is nested under a table (no bare options).

```toml
[table1]
option = "value"

[table2]
option = "value"

[table3.subtable1]
option = "value"
```

## RAMALAMA TABLE
The `ramalama` table contains default runtime and CLI settings.

`[[ramalama]]`

**Core runtime options:**

**api**="none": Unified API layer for Inference, RAG, Agents, Tools, Safety, Evals, and Telemetry.
Options: `llama-stack`, `none`.

**api_key**="": OpenAI-compatible API key.
This value can also be set via `RAMALAMA_API_KEY`.

**Model conversion options:**

**carimage**="registry.access.redhat.com/ubi10-micro:latest": OCI model car image used when building and pushing `--type=car` models.

**container**=true: Run RamaLama in a container by default.
Override via `RAMALAMA_IN_CONTAINER`.

**convert_type**="raw": Default object type when converting models.
Options: `artifact`, `car`, `raw`.

| Type | Description |
| --- | --- |
| `artifact` | Store AI models as OCI artifacts |
| `car` | Traditional OCI image with model under `/models` |
| `raw` | OCI image with only the model and `model.file` link file at `/` |

**ctx_size**=0: Prompt context size. 0 means use the model default.

**Container and engine options:**

**engine**="podman": Container engine.
Valid options: podman, docker.
Override via `RAMALAMA_CONTAINER_ENGINE`.

**env**=[]: Environment variables added to the container runtime environment.
Example: "LLAMA_ARG_THREADS=10".

**host**="::" | "0.0.0.0"

IP address for llama.cpp to listen on.
Defaults to "::" (dual-stack) on systems with IPv6 support, "0.0.0.0" (IPv4-only) otherwise.

**image**="quay.io/ramalama/ramalama:latest"

OCI container image to run with the specified AI model
RAMALAMA_IMAGE environment variable overrides this field.

`[[ramalama.images]]`

User-override entries for runtime-specific container images.

**keep_groups**=false: Pass `--group-add keep-groups` when using podman.
Useful in some rootless GPU access setups.

**log_level**=warning: Logging level.
Valid values: `debug`, `info`, `warning`, `error`, `critical`.
`--debug` overrides this field and forces debug logging.

**max_tokens**=0: Maximum number of tokens to generate.
Set to 0 for unlimited output.

**Serving options:**

**prefix**="": Default prompt prefix for `chat` and `run`.

| Container Engine | Prefix |
| --- | --- |
| Podman | "🦭 > " |
| Docker | "🐋 > " |
| No Engine | "🦙 > " |
| No emoji support | "> " |

**port**="8080": Initial port for service allocation.
RamaLama attempts a range of 101 ports starting from this value.

**pull**="newer": Pull policy for runtime images.

- `always`: Always pull, fail on pull error.
- `missing`: Pull only when local image is missing.
- `never`: Never pull; use local image only.
- `newer`: Pull when remote digest differs; suppress pull errors if local image exists.

**RAG and storage options:**

**rag_image**="quay.io/ramalama/ramalama-rag"

OCI container image used for RAG processing (doc2rag and rag_framework).
Can also be overridden with the `--rag-image` flag on the command line or the
RAMALAMA_RAG_IMAGE environment variable.

**stack_image**="quay.io/ramalama/llama-stack"

OCI container image used for running llama-stack server.
Can also be overridden with the `--stack-image` flag on the command line or the
RAMALAMA_STACK_IMAGE environment variable.

`[[ramalama.tools_images]]`

User-override entries for GPU-specific tools container images used for GGUF
conversion. Built-in GPU defaults (CUDA, ROCm, Intel) are defined internally;
entries here override those defaults:

  CUDA_VISIBLE_DEVICES   = "quay.io/ramalama/cuda-tools"
  HIP_VISIBLE_DEVICES    = "quay.io/ramalama/rocm-tools"
  INTEL_VISIBLE_DEVICES  = "quay.io/ramalama/intel-gpu-tools"

Can also be overridden with the `--tools-image` flag on the command line or the
RAMALAMA_TOOLS_IMAGE environment variable.

**runtime**="llama.cpp": Inference runtime.
Options: `llama.cpp`, `vllm`, `mlx`.

**selinux**=false: Enable SELinux container separation enforcement.

**store**="$HOME/.local/share/ramalama": Directory where AI models and data are stored.

**summarize_after**=4: Automatically summarize chat history after N messages to limit context growth.
Set to 0 to disable.

**Transport and HTTP options:**

**transport**="ollama": Default transport used for pull/push operations.
Options: `oci`, `ollama`, `huggingface`.
Override via `RAMALAMA_TRANSPORT`.

`[[ramalama.http_client]]`

**max_retries**=5: Maximum number of retries for failed downloads.

**max_retry_delay**=30: Maximum delay (seconds) between retry attempts.

## RAMALAMA.PROVIDER TABLE
The `ramalama.provider` table configures hosted API providers.

`[[ramalama.provider]]`

**openai:**
Configuration block for the OpenAI hosted provider.

`[[ramalama.provider.openai]]`

**api_key**=""

`ramalama.provider.openai.api_key` overrides `RAMALAMA_API_KEY` when set.

## RAMALAMA.BENCHMARKS TABLE
The `ramalama.benchmarks` table contains benchmark settings.

`[[ramalama.benchmarks]]`

`storage_folder` defaults to `<default store>/benchmarks`.

By default, benchmark results are saved in the configured store directory under benchmarks/.
If you change `ramalama.store`, set `ramalama.benchmarks.storage_folder` explicitly if needed.

## RAMALAMA.USER TABLE
The `ramalama.user` table contains user preferences.

`[[ramalama.user]]`

**no_missing_gpu_prompt**=false

When `no_missing_gpu_prompt = true`, RamaLama suppresses the interactive prompt on macOS Podman VMs without GPU acceleration (for example, `applehv`).
This value can also be set via `RAMALAMA_USER__NO_MISSING_GPU_PROMPT`.

## RAMALAMA.RUNTIMES TABLE
Runtime-specific configuration. Each runtime plugin defines its own config section
under `[ramalama.runtimes.<name>]`. The key name uses underscores (e.g. `llama_cpp`
for the "llama.cpp" runtime).

`[[ramalama.runtimes.llama_cpp]]`

**backend**="auto": GPU backend to use for inference.
This setting affects which container image is selected and how GPU resources are utilized.

Valid options: `auto`, `vulkan`, `rocm`, `cuda`, `sycl`, `openvino`, `cann`, `musa`.

- **auto** (default): Automatically selects the preferred backend based on detected GPU:
  - AMD GPUs: vulkan (Linux/macOS) or rocm (Windows)
  - NVIDIA GPUs: cuda
  - Intel GPUs: vulkan (Linux/macOS) or sycl (Windows); openvino available as explicit option
  - Ascend NPUs: cann
  - MUSA GPUs: musa
  - No GPU: vulkan (CPU fallback)

- **vulkan**: Use Vulkan-based inference (compatible with AMD, Intel, and CPU)
- **rocm**: Use AMD ROCm backend (AMD GPUs only)
- **cuda**: Use NVIDIA CUDA backend (NVIDIA GPUs only)
- **sycl**: Use Intel SYCL/oneAPI backend (Intel GPUs only)
- **openvino**: Use Intel OpenVINO backend (Intel GPUs only); uses `quay.io/ramalama/openvino`
- **cann**: Use Huawei CANN backend (Ascend NPUs only); uses `quay.io/ramalama/cann`
- **musa**: Use Moore Threads MUSA backend (MUSA GPUs only); uses `quay.io/ramalama/musa`

**Platform-specific behavior**: On Windows, vulkan is not supported on WSL2, so vendor-specific backends (rocm for AMD, sycl for Intel) are automatically preferred when using `backend="auto"`.

Example configuration:

    [ramalama.runtimes.llama_cpp]
    backend = "vulkan"  # Force Vulkan for all GPUs

**cache_reuse**=256: Min chunk size to attempt reusing from the cache via KV shifting.

**gguf_quantization_mode**="Q4_K_M": Quantization mode used when creating OCI-formatted AI models.
Options: `Q2_K`, `Q3_K_S`, `Q3_K_M`, `Q3_K_L`, `Q4_0`, `Q4_K_S`, `Q4_K_M`, `Q5_0`, `Q5_K_S`, `Q5_K_M`, `Q6_K`, `Q8_0`.

**ngl**=-1: Number of layers to offload to the GPU. Set to -1 to offload all layers.

**temp**="0.8": Response sampling temperature.
- Lower values: more deterministic output
- Higher values: more creative output (higher hallucination risk)

**thinking**=true: Enable/disable thinking mode in reasoning models.

**threads**=4: Number of CPU threads to use for inference.
Default is half the available CPU cores (minimum 4).

`[[ramalama.runtimes.mlx]]`

**temp**="0.8": Response sampling temperature.
- Lower values: more deterministic output
- Higher values: more creative output (higher hallucination risk)
