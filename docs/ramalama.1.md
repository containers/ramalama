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

Running in containers eliminates the need for users to configure the host
system for AI. After the initialization, RamaLama runs the AI Models within a
container based on the OCI image. RamaLama pulls container image specific to
the GPUs discovered on the host system. These images are tied to the minor
version of RamaLama. For example RamaLama version 1.2.3 on an NVIDIA system
pulls quay.io/ramalama/cuda:1.2. To override the default image use the
`--image` option.

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

RamaLama pulls AI Models from model registries. Starting a chatbot or a rest API service from a simple single command. Models are treated similarly to how Podman and Docker treat container images.

When both Podman and Docker are installed, RamaLama defaults to Podman, The `RAMALAMA_CONTAINER_ENGINE=docker` environment variable can override this behaviour. When neither are installed RamaLama attempts to run the model with software on the local system.

Note:

On MacOS systems that use Podman for containers, configure the Podman machine
to use the `libkrun` machine provider. The `libkrun` provider enables
containers within the Podman Machine access to the Mac's GPU.
See **[ramalama-macos(7)](ramalama-macos.7.md)** for further information.

Note:

On systems with NVIDIA GPUs, see **[ramalama-cuda(7)](ramalama-cuda.7.md)** to correctly configure the host system.

Default settings for flags are defined in **[ramalama.conf(5)](ramalama.conf.5.md)**.

## SECURITY

### Test and run your models more securely

Because RamaLama defaults to running AI models inside of rootless containers using Podman on Docker. These containers isolate the AI models from information on the underlying host. With RamaLama containers, the AI model is mounted as a volume into the container in read/only mode. This results in the process running the model, llama.cpp or vLLM, being isolated from the host.  In addition, since `ramalama run` uses the --network=none option, the container can not reach the network and leak any information out of the system. Finally, containers are run with --rm options which means that any content written during the running of the container is wiped out when the application exits.

### Here’s how RamaLama delivers a robust security footprint:

    ✅ Container Isolation – AI models run within isolated containers, preventing direct access to the host system.
    ✅ Read-Only Volume Mounts – The AI model is mounted in read-only mode, meaning that processes inside the container cannot modify host files.
    ✅ No Network Access – ramalama run is executed with --network=none, meaning the model has no outbound connectivity for which information can be leaked.
    ✅ Auto-Cleanup – Containers run with --rm, wiping out any temporary data once the session ends.
    ✅ Drop All Linux Capabilities – No access to Linux capabilities to attack the underlying host.
    ✅ No New Privileges – Linux Kernel feature which disables container processes from gaining additional privileges.

## MODEL TRANSPORTS

RamaLama supports multiple AI model registries types called transports. Supported transports:

| Transports    | Prefix | Web Site                                            |
| ------------- | ------ | --------------------------------------------------- |
| URL based     | https://, http://, file:// | `https://web.site/ai.model`, `file://tmp/ai.model`|
| HuggingFace   | huggingface://, hf://, hf.co/ | [`huggingface.co`](https://www.huggingface.co)|
| ModelScope    | modelscope://, ms:// | [`modelscope.cn`](https://modelscope.cn/)|
| Ollama        | ollama:// | [`ollama.com`](https://www.ollama.com)|
| OCI Container Registries | oci:// | [`opencontainers.org`](https://opencontainers.org)|
|||Examples: [`quay.io`](https://quay.io),  [`Docker Hub`](https://docker.io),[`Artifactory`](https://artifactory.com)|

RamaLama uses to the Ollama registry transport. This default can be overridden in the `ramalama.conf` file or via the RAMALAMA_TRANSPORTS
environment. `export RAMALAMA_TRANSPORT=huggingface` Changes RamaLama to use huggingface transport.

Modify individual model transports by specifying the `huggingface://`, `oci://`, `ollama://`, `https://`, `http://`, `file://` prefix to the model.

URL support means if a model is on a web site or even on your local system, you can run it directly.

ramalama pull `huggingface://`afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k.gguf

ramalama run `file://`$HOME/granite-7b-lab-Q4_K_M.gguf

To make it easier for users, RamaLama uses shortname files, which container
alias names for fully specified AI Models allowing users to specify the shorter
names when referring to models. RamaLama reads shortnames.conf files if they
exist . These files contain a list of name value pairs for specification of
the model. The following table specifies the order which RamaLama reads the files
. Any duplicate names that exist override previously defined shortnames.

| Shortnames type | Path                                            |
| --------------- | ----------------------------------------  |
| Distribution    | /usr/share/ramalama/shortnames.conf       |
| Local install   | /usr/local/share/ramalama/shortnames.conf |
| Administrators  | /etc/ramamala/shortnames.conf             |
| Users           | $HOME/.config/ramalama/shortnames.conf    |

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

#### **--help**, **-h**
show this help message and exit

#### **--image**=IMAGE
OCI container image to run with specified AI model. RamaLama defaults to use
images based on the accelerator it discovers. For example:
`quay.io/ramalama/ramalama`. See the table below for all default images.
The default image tag is based on the minor version of the RamaLama package.
Version 0.10.0 of RamaLama pulls $IMAGE:0.10 from the quay.io/ramalama OCI repository. The --image option overrides this default.

The default can be overridden in the ramalama.conf file or via the
RAMALAMA_IMAGE environment variable. `export RAMALAMA_IMAGE=quay.io/ramalama/aiimage:1.2` tells
RamaLama to use the `quay.io/ramalama/aiimage:1.2` image.

#### **--keep-groups**
pass --group-add keep-groups to podman (default: False)
Needed to access the gpu on some systems, but has an impact on security, use with caution.

#### **--nocontainer**
Do not run RamaLama in the default container (default: False)
The default can be overridden in the ramalama.conf file.

Note: OCI images cannot be used with the --nocontainer option. This option disables the following features: GPU acceleration, containerized environment isolation, and dynamic resource allocation. For a complete list of affected features, please see the RamaLama documentation at [link-to-feature-list].

#### **--quiet**
Decrease output verbosity.

#### **--runtime**=*llama.cpp* | *vllm*
specify the runtime to use, valid options are 'llama.cpp' and 'vllm' (default: llama.cpp)
The default can be overridden in the ramalama.conf file.

#### **--store**=STORE
store AI Models in the specified directory (default rootless: `$HOME/.local/share/ramalama`, default rootful: `/var/lib/ramalama`)
The default can be overridden in the ramalama.conf file.

## COMMANDS

| Command                                           | Description                                                |
| ------------------------------------------------- | ---------------------------------------------------------- |
| [ramalama-bench(1)](ramalama-bench.1.md)          | benchmark specified AI Model                               |
| [ramalama-chat(1)](ramalama-chat.1.md)            |  OpenAI chat with the specified REST API URL                |
| [ramalama-containers(1)](ramalama-containers.1.md)| list all RamaLama containers                               |
| [ramalama-convert(1)](ramalama-convert.1.md)      | convert AI Models from local storage to OCI Image          |
| [ramalama-info(1)](ramalama-info.1.md)            | display RamaLama configuration information                 |
| [ramalama-inspect(1)](ramalama-inspect.1.md)      | inspect the specified AI Model                             |
| [ramalama-list(1)](ramalama-list.1.md)            | list all downloaded AI Models                              |
| [ramalama-login(1)](ramalama-login.1.md)          | login to remote registry                                   |
| [ramalama-logout(1)](ramalama-logout.1.md)        | logout from remote registry                                |
| [ramalama-perplexity(1)](ramalama-perplexity.1.md)| calculate the perplexity value of an AI Model              |
| [ramalama-pull(1)](ramalama-pull.1.md)            | pull AI Models from Model registries to local storage      |
| [ramalama-push(1)](ramalama-push.1.md)            | push AI Models from local storage to remote registries     |
| [ramalama-rag(1)](ramalama-rag.1.md)              | generate and convert Retrieval Augmented Generation (RAG) data from provided documents into an OCI Image |
| [ramalama-rm(1)](ramalama-rm.1.md)                | remove AI Models from local storage                        |
| [ramalama-run(1)](ramalama-run.1.md)              | run specified AI Model as a chatbot                        |
| [ramalama-serve(1)](ramalama-serve.1.md)          | serve REST API on specified AI Model                       |
| [ramalama-stop(1)](ramalama-stop.1.md)            | stop named container that is running AI Model              |
| [ramalama-version(1)](ramalama-version.1.md)      | display version of RamaLama                                |

## CONFIGURATION FILES

**ramalama.conf** (`/usr/share/ramalama/ramalama.conf`, `/etc/ramalama/ramalama.conf`, `$HOME/.config/ramalama/ramalama.conf`)

RamaLama has builtin defaults for command line options. These defaults can be overridden using the ramalama.conf configuration files.

Distributions ship the `/usr/share/ramalama/ramalama.conf` file with their default settings. Administrators can override fields in this file by creating the `/etc/ramalama/ramalama.conf` file.  Users can further modify defaults by creating the `$HOME/.config/ramalama/ramalama.conf` file. RamaLama merges its builtin defaults with the specified fields from these files, if they exist. Fields specified in the users file override the administrator's file, which overrides the distribution's file, which override the built-in defaults.

RamaLama uses builtin defaults if no ramalama.conf file is found.

If the **RAMALAMA_CONFIG** environment variable is set, then its value is used for the ramalama.conf file rather than the default.

## ENVIRONMENT VARIABLES

RamaLama default behaviour can also be overridden via environment variables,
although the recommended way is to use the ramalama.conf file.

| ENV Name                  | Description                                |
| ------------------------- | ------------------------------------------ |
| RAMALAMA_CONFIG           | specific configuration file to be used     |
| RAMALAMA_CONTAINER_ENGINE | container engine (Podman/Docker) to use    |
| RAMALAMA_FORCE_EMOJI      | define whether `ramalama run` uses EMOJI   |
| RAMALAMA_IMAGE            | container image to use for serving AI Model|
| RAMALAMA_IN_CONTAINER     | Run RamaLama in the default container      |
| RAMALAMA_STORE            | location to store AI Models                |
| RAMALAMA_TRANSPORT        | default AI Model transport (ollama, huggingface, OCI) |

## SEE ALSO
**[podman(1)](https://github.com/containers/podman/blob/main/docs/source/markdown/podman.1.md)**, **docker(1)**, **[ramalama.conf(5)](ramalama.conf.5.md)**, **[ramalama-cuda(7)](ramalama-cuda.7.md)**, **[ramalama-macos(7)](ramalama-macos.7.md)**


## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
