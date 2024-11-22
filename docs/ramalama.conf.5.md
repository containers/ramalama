% ramalama.conf 5 RamaLama AI tool configuration file

# NAME
ramalama.conf - These configuration files specifies default
configuration options and command-line flags for RamaLama.

# DESCRIPTION
RamaLama reads the ramalama.conf file, if it exists
and modify the defaults for running RamaLama on the host. ramalama.conf uses
a TOML format that can be easily modified and versioned.

RamaLama reads the he following paths for global configuration that effects all users.

| Paths       |
| -----------------------------------       |
| __/usr/share/ramalama/ramalama.conf__     |
| __/etc/ramalama/ramalama.conf__           |
| __/etc/ramalama/ramalama.conf.d/\*.conf__ |

For user specific configuration it reads

| Paths                                       | Exception |
| -----------------------------------         | ------------------------------ |
| __$XDG_CONFIG_HOME/ramalama/ramalama.conf__ |                                        |
| __$XDG_CONFIG_HOME/ramalama/ramalama.conf.d/\*.conf__ |                              |
| __$HOME/.config/ramalama/ramalama.conf.d/\*.conf__ | When `$XDG_CONFIG_HOME` not set |

Fields specified in ramalama conf override the default options, as well as
options in previously read ramalama.conf files.

Config files in the `.d` directories, are added in alpha numeric sorted order and must end in `.conf`.

## ENVIRONMENT VARIABLES
If the `RAMALAMA_CONF` environment variable is set, all system and user
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

[ramalama]

**carimage**="registry.access.redhat.com/ubi9-micro:latest"

OCI model car image

Image to be used when building and pushing --type=car models

**container**=true

Run RamaLama in the default container.
RAMALAMA_IN_CONTAINER environment variable overrides this field.

**ctx_size**=2048

Size of the prompt context (0 = loaded from model)

**engine**="podman"

Run RamaLama using the specified container engine.
Valid options are: Podman and Docker
This field can be overridden by the RAMALAMA_CONTAINER_ENGINE environment variable.

**host**="0.0.0.0"

IP address for llama.cpp to listen on.

**image**="quay.io/ramalama/ramalama:latest"

OCI container image to run with the specified AI model
RAMALAMA_IMAGE environment variable overrides this field.

**port**="8080"

Specify default port for services to listen on

**runtime**="llama.cpp"

Specify the AI runtime to use; valid options are 'llama.cpp' and 'vllm' (default: llama.cpp)
Options: llama.cpp, vllm

**store**="$HOME/.local/share/ramalama"

Store AI Models in the specified directory

**temp**="0.8"
Temperature of the response from the AI Model
llama.cpp explains this as:

    The lower the number is, the more deterministic the response.

    The higher the number is the more creative the response is, but moee likely to hallucinate when set too high.

        Usage: Lower numbers are good for virtual assistants where we need deterministic responses. Higher numbers are good for roleplay or creative tasks like editing stories

**transport**="ollama"

Specify the default transport to be used for pulling and pushing of AI Models.
Options: oci, ollama, huggingface.
RAMALAMA_TRANSPORT environment variable overrides this field.
