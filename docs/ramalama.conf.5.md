% ramalama.conf 5 RamaLama AI tool configuration file

# NAME
ramalama.conf - These configuration files specifies default
configuration options and command-line flags for RamaLama.

# DESCRIPTION
RamaLama reads the ramalama.conf file, if it exists
and modify the defaults for running RamaLama on the host. ramalama.conf uses
a TOML format that can be easily modified and versioned.

RamaLama reads the he following paths for global configuration that effects all users.

| Paths       | Exception |
| ----------------------------------- | ----------------------------------- |
| __/usr/share/ramalama/ramalama.conf__       | On Linux |
| __/usr/local/share/ramalama/ramalama.conf__ | On Linux |
| __/etc/ramalama/ramalama.conf__             | On Linux |
| __/etc/ramalama/ramalama.conf.d/\*.conf__   | On Linux |
| __$HOME/.local/.pipx/venvs/usr/share/ramalama/ramalama.conf__ |On pipx installed macOS  |


For user specific configuration it reads

| Paths                                       | Exception |
| -----------------------------------         | ------------------------------ |
| __$XDG_CONFIG_HOME/ramalama/ramalama.conf__           |       |
| __$XDG_CONFIG_HOME/ramalama/ramalama.conf.d/\*.conf__ |       |
| __$HOME/.config/ramalama/ramalama.conf__ | `$XDG_CONFIG_HOME` not set |
| __$HOME/.config/ramalama/ramalama.conf.d/\*.conf__ | `$XDG_CONFIG_HOME` not set |

Fields specified in ramalama conf override the default options, as well as
options in previously read ramalama.conf files.

Config files in the `.d` directories, are added in alpha numeric sorted order and must end in `.conf`.

## ENVIRONMENT VARIABLES
If the `RAMALAMA_CONFIG` environment variable is set, all system and user
config files are ignored and only the specified config file is loaded.

# FORMAT
The [TOML format][toml] is used as the encoding of the configuration file.
Every option is nested under its table. No bare options are used. The format of
TOML can be simplified to:

    [table1]
    option = value

    [table2]
    option = value

    [table3]
    option = value

    [table3.subtable1]
    option = value

## RAMALAMA TABLE
The ramalama table contains settings to configure and manage the OCI runtime.

`[[ramalama]]`

**api**="none"

Unified API layer for Inference, RAG, Agents, Tools, Safety, Evals, and Telemetry.
Options: llama-stack, none

**carimage**="registry.access.redhat.com/ubi10-micro:latest"

OCI model car image

Image to be used when building and pushing --type=car models

**container**=true

Run RamaLama in the default container.
RAMALAMA_IN_CONTAINER environment variable overrides this field.

**ctx_size**=2048

Size of the prompt context (0 = loaded from model)

**env=[]

Environment variables to be added to the environment used when running in a container engine (e.g., Podman, Docker). For example "LLAMA_ARG_THREADS=10".

**engine**="podman"

Run RamaLama using the specified container engine.
Valid options are: Podman and Docker
This field can be overridden by the RAMALAMA_CONTAINER_ENGINE environment variable.

**host**="0.0.0.0"

IP address for llama.cpp to listen on.

**image**="quay.io/ramalama/ramalama:latest"

OCI container image to run with the specified AI model
RAMALAMA_IMAGE environment variable overrides this field.

`[[ramalama.images]]`
  HIP_VISIBLE_DEVICES    = "quay.io/ramalama/rocm"
  CUDA_VISIBLE_DEVICES   = "quay.io/ramalama/cuda"
  ASAHI_VISIBLE_DEVICES  = "quay.io/ramalama/asahi"
  INTEL_VISIBLE_DEVICES  = "quay.io/ramalama/intel-gpu"
  ASCEND_VISIBLE_DEVICES = "quay.io/ramalama/cann"
  MUSA_VISIBLE_DEVICES   = "quay.io/ramalama/musa"

Alternative images to use when RamaLama recognizes specific hardware

**keep_groups**=false

Pass `--group-add keep-groups` to podman, when using podman.
In some cases this is needed to access the gpu from a rootless container

**ngl**=-1

number of gpu layers, 0 means CPU inferencing, 999 means use max layers (default: -1)
The default -1, means use whatever is automatically deemed appropriate (0 or 999)

**prefix**=""
Specify default prefix for chat and run command. By default the prefix
is based on the container engine used.

| Container Engine| Prefix  |
| --------------- | ------- |
| Podman          | "🦭 > " |
| Docker          | "🐋 > " |
| No Engine       | "🦙 > " |
| No EMOJI support| "> "    |

**port**="8080"

Specify default port for services to listen on

**pull**="newer"

- **always**: Always pull the image and throw an error if the pull fails.
- **missing**: Only pull the image when it does not exist in the local containers storage. Throw an error if no image is found and the pull fails.
- **never**: Never pull the image but use the one from the local containers storage. Throw an error when no image is found.
- **newer**: Pull if the image on the registry is newer than the one in the local containers storage. An image is considered to be newer when the digests are different. Comparing the time stamps is prone to errors. Pull errors are suppressed if a local image was found.

**rag_format**="qdrant"

Specify the default output format for output of the `ramalama rag` command
Options: json, markdown, qdrant

**runtime**="llama.cpp"

Specify the AI runtime to use; valid options are 'llama.cpp', 'vllm', and 'mlx' (default: llama.cpp)
Options: llama.cpp, vllm, mlx

**selinux**=false

SELinux container separation enforcement

**store**="$HOME/.local/share/ramalama"

Store AI Models in the specified directory

**temp**="0.8"
Temperature of the response from the AI Model
llama.cpp explains this as:

    The lower the number is, the more deterministic the response.

    The higher the number is the more creative the response is, but more likely to hallucinate when set too high.

        Usage: Lower numbers are good for virtual assistants where we need deterministic responses. Higher numbers are good for roleplay or creative tasks like editing stories

**threads**=-1

maximum number of cpu threads to use for inferencing
The default -1, uses the default of the underlying implementation

**transport**="ollama"

Specify the default transport to be used for pulling and pushing of AI Models.
Options: oci, ollama, huggingface.
RAMALAMA_TRANSPORT environment variable overrides this field.
