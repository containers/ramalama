% ramalama 1

## NAME
ramalama - Simple management tool for working with AI Models

## SYNOPSIS
**ramalama** [*options*] *command*

## DESCRIPTION
RamaLama : The goal of RamaLama is to make AI boring.

RamaLama tool facilitates local management and serving of AI Models.

On first run RamaLama inspects your system for GPU support, falling back to CPU support if no GPUs are present.

RamaLama uses container engines like Podman or Docker to pull the appropriate OCI image with all of the software necessary to run an AI Model for your systems setup.

Running in containers eliminates the need for users to configure the host system for AI. After the initialization, RamaLama runs the AI Models within a container based on the OCI image.

RamaLama pulls AI Models from model registries. Starting a chatbot or a rest API service from a simple single command. Models are treated similarly to how Podman and Docker treat container images.

When both Podman and Docker are installed, RamaLama defaults to Podman, The `RAMALAMA_CONTAINER_ENGINE=docker` environment variable can override this behavior. When neither are installed RamaLama attempts to run the model with software on the local system.

Note:

On Macs with Arm support and Podman, the Podman machine must be
configured to use the krunkit VM Type. This allows the Mac's GPU to be
used within the VM.

Default settings for flags are defined in `ramalama.conf(5)`.

RamaLama supports multiple AI model registries types called transports. Supported transports:

## TRANSPORTS

| Transports    | Web Site                                            |
| ------------- | --------------------------------------------------- |
| HuggingFace   | [`huggingface.co`](https://www.huggingface.co)      |
| Ollama        | [`ollama.com`](https://www.ollama.com)              |
| OCI Container Registries | [`opencontainers.org`](https://opencontainers.org)|
||Examples: [`quay.io`](https://quay.io),  [`Docker Hub`](https://docker.io), and [`Artifactory`](https://artifactory.com)|

RamaLama can also pull directly using URL syntax.

http://, https:// and file://.

This means if a model is on a web site or even on your local system, you can run it directly.

RamaLama uses the Ollama registry transport by default. The default can be overridden in the ramalama.conf file or use the RAMALAMA_TRANSPORTS
environment. `export RAMALAMA_TRANSPORT=huggingface` Changes RamaLama to use huggingface transport.

Individual model transports can be modifies when specifying a model via the `huggingface://`, `oci://`, `ollama://`, `https://`, `http://`, `file://` prefix.

ramalama pull `huggingface://`afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k.gguf

ramalama run `file://`$HOME/granite-7b-lab-Q4_K_M.gguf

To make it easier for users, RamaLama uses shortname files, which container
alias names for fully specified AI Models allowing users to specify the shorter
names when referring to models. RamaLama reads shortnames.conf files if they
exist . These files contain a list of name value pairs for specification of
the model. The following table specifies the order which RamaLama reads the files
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
run RamaLama in the default container. Default is `true` unless overridden in the ramalama.conf file.
The environment variable "RAMALAMA_IN_CONTAINER=false" can also change the default.

#### **--debug**
print debug messages

#### **--dryrun**
show container runtime command without executing it (default: False)

#### **--engine**
run RamaLama using the specified container engine. Default is `podman` if installed otherwise docker.
The default can be overridden in the ramalama.conf file or via the RAMALAMA_CONTAINER_ENGINE environment variable.

#### **--gpu**
offload the workload to the GPU (default: False)

#### **--help**, **-h**
show this help message and exit

#### **--image**=IMAGE
OCI container image to run with specified AI model. By default RamaLama uses
`quay.io/ramalama/ramalama:latest`. The --image option allows users to override
the default.

The default can be overridden in the ramalama.conf file or via the the
RAMALAMA_IMAGE environment variable. `export RAMALAMA_TRANSPORT=quay.io/ramalama/aiimage:latest` tells
RamaLama to use the `quay.io/ramalama/aiimage:latest` image.

#### **--nocontainer**
do not run RamaLama in the default container (default: False)
The default can be overridden in the ramalama.conf file.

#### **--runtime**=*llama.cpp* | *vllm*
specify the runtime to use, valid options are 'llama.cpp' and 'vllm' (default: llama.cpp)
The default can be overridden in the ramalama.conf file.

#### **--store**=STORE
store AI Models in the specified directory (default rootless: `$HOME/.local/share/ramalama`, default rootful: `/var/lib/ramalama`)
The default can be overridden in the ramalama.conf file.

## COMMANDS

| Command                                           | Description                                                |
| ------------------------------------------------- | ---------------------------------------------------------- |
| [ramalama-containers(1)](ramalama-containers.1.md)| list all RamaLama containers                               |
| [ramalama-info(1)](ramalama-info.1.md)            | Display RamaLama configuration information                 |
| [ramalama-list(1)](ramalama-list.1.md)            | list all downloaded AI Models                              |
| [ramalama-login(1)](ramalama-login.1.md)          | login to remote registry                                   |
| [ramalama-logout(1)](ramalama-logout.1.md)        | logout from remote registry                                |
| [ramalama-pull(1)](ramalama-pull.1.md)            | pull AI Models from Model registries to local storage      |
| [ramalama-push(1)](ramalama-push.1.md)            | push AI Models from local storage to remote registries     |
| [ramalama-rm(1)](ramalama-rm.1.md)                | remove AI Models from local storage                        |
| [ramalama-run(1)](ramalama-run.1.md)              | run specified AI Model as a chatbot                        |
| [ramalama-serve(1)](ramalama-serve.1.md)          | serve REST API on specified AI Model                       |
| [ramalama-stop(1)](ramalama-stop.1.md)            | stop named container that is running AI Model              |
| [ramalama-version(1)](ramalama-version.1.md)      | display version of RamaLama
## CONFIGURATION FILES


## SEE ALSO
**[podman(1)](https://github.com/containers/podman/blob/main/docs/podman.1.md)**, **docker(1)**, **[ramalama.conf(5)](ramalama.conf.5.md)**

## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
