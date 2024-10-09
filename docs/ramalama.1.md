% ramalama 1

## NAME
ramalama - Simple management tool for working with AI Models

## SYNOPSIS
**ramalama** [*options*] *command*

## DESCRIPTION
RamaLama : The goal of RamaLama is to make AI boring.

On first run RamaLama inspects your system for GPU support, falling back to CPU
support if no GPUs are present. RamaLama uses container engines like Podman or
Docker to pull the appropriate OCI image with all of the software necessary to
run an AI Model for your systems setup. This eliminates the need for the user
to configure the system for AI themselves. After the initialization, RamaLama
will run the AI Models within a container based on the OCI image.

RamaLama first pulls AI Models from model registires. It then start a chatbot
or a service as a rest API from a simple single command. Models are treated
similarly to the way that Podman or Docker treat container images.

If you have both Podman and Docker installed, RamaLama defaults to Podman, use
the `RAMALAMA_CONTAINER_ENGINE=docker` environment variable to override this
behaviour.

RamaLama supports multiple AI model registries types called transports.
Supported transports:


## TRANSPORTS

| Transports    | Web Site                                            |
| ------------- | --------------------------------------------------- |
| HuggingFace   | [`huggingface.co`](https://www.huggingface.co)      |
| Ollama        | [`ollama.com`](https://www.ollama.com)              |
| OCI Container Registries | [`opencontainers.org`](https://opencontainers.org)|
||Examples: [`quay.io`](https://quay.io),  [`Docker Hub`](https://docker.io), and [`Artifactory`](https://artifactory.com)|

RamaLama uses the Ollama registry transport by default. Use the RAMALAMA_TRANSPORTS environment variable to modify the default. `export RAMALAMA_TRANSPORT=huggingface` Changes RamaLama to use huggingface transport.

Individual model transports can be modifies when specifying a model via the `huggingface://`, `oci://`, or `ollama://` prefix.

ramalama pull `huggingface://`afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k.gguf

To make it easier for users, RamaLama uses shortname files, which container
alias names for fully specified AI Models allowing users to specify the shorter
names when referring to models. RamaLama reads shortnames.conf files if they
exist . These files contain a list of name value pairs for specification of
the model. The following table specifies the order which Ramama reads the files
. Any duplicate names that exist override previously defined shortnames.

| Shortnames type | Path                                            |
| --------------- | ---------------------------------------- |
| Distribution    | /usr/share/ramalama/shortnames.conf      |
| Administrators  | /etc/ramamala/shortnames.conf            |
| Users           | $HOME/.config/ramalama/shortnames.conf   |

```code
$ cat /usr/share/ramalama/shortnames.conf
[shortnames]
  "tiny" = "ollama://tinyllama"
  "granite" = "huggingface://instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf"
  "granite:7b" = "huggingface://instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf"
  "ibm/granite" = "huggingface://instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf"
  "merlinite" = "huggingface://instructlab/merlinite-7b-lab-GGUF/merlinite-7b-lab-Q4_K_M.gguf"
  "merlinite:7b" = "huggingface://instructlab/merlinite-7b-lab-GGUF/merlinite-7b-lab-Q4_K_M.gguf"
...
```
**ramalama [GLOBAL OPTIONS]**

## GLOBAL OPTIONS

#### **--container**
run RamaLama in the default container (default: True)
use environment variable "RAMALAMA_IN_CONTAINER=false" to change default.

#### **--dryrun**
show container runtime command without executing it (default: False)

#### **--help**, **-h**
show this help message and exit

#### **--image**=IMAGE
OCI container image to run with specified AI model. By default RamaLama
attempts to use the best AI OCI image based on GPU on the local system.
The --image option allows users to override the default.

The RAMALAMA_IMAGE environment variable can be used to modify the default
image. `export RAMALAMA_TRANSPORT=quay.io/ramalama/aiimage:latest` tells
RamaLama to use the `quay.io/ramalama/aiimage:latest` image.

#### **--nocontainer**
do not run RamaLama in the default container (default: False)

#### **--runtime**
specify the runtime to use, valid options are 'llama.cpp' and 'vllm' (default: llama.cpp)

#### **--store**=STORE
store AI Models in the specified directory (default rootless: `$HOME/.local/share/ramalama`, default rootful: `/var/lib/ramalama`)

## COMMANDS

| Command                                           | Description                                                |
| ------------------------------------------------- | ---------------------------------------------------------- |
| [ramalama-containers(1)](ramalama-containers.1.md)| list all RamaLama containers                               |
| [ramalama-list(1)](ramalama-list.1.md)            | list all downloaded AI Models                              |
| [ramalama-login(1)](ramalama-login.1.md)          | login to remote registry                                   |
| [ramalama-logout(1)](ramalama-logout.1.md)        | logout from remote registry                                |
| [ramalama-pull(1)](ramalama-pull.1.md)            | pull AI Models from Model registries to local storage      |
| [ramalama-push(1)](ramalama-push.1.md)            | push AI Models from local storage to remote registries     |
| [ramalama-rm(1)](ramalama-rm.1.md)                | remove AI Models from local storage                         |
| [ramalama-run(1)](ramalama-run.1.md)              | run specified AI Model as a chatbot                        |
| [ramalama-serve(1)](ramalama-serve.1.md)          | serve REST API on specified AI Model                       |
| [ramalama-stop(1)](ramalama-stop.1.md)            | stop named container that is running AI Model              |
| [ramalama-version(1)](ramalama-version.1.md)      | display version of RamaLama
## CONFIGURATION FILES


## SEE ALSO
**[podman(1)](https://github.com/containers/podman/blob/main/docs/podman.1.md)**

## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
