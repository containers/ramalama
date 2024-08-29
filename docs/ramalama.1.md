% ramalama 1

## NAME
ramalama - Simple management tool for working with AI Models

## SYNOPSIS
**ramalama** [*options*] *command*

## DESCRIPTION
Ramalama : The goal of ramalama is to make AI boring. Ramalama can pull an AI
Model from model registires and start a chatbot or serve as a rest API from a
simple single command. It treats Models similar to the way that Podman or
Docker treat container images.

Ramalama runs models with a specially designed container image containing all
of the tooling required to run the Model. Users d ont need to pre-configure
the host system.

Ramalama supports multiple model registries types called transports.
Supported transports:

* HuggingFace : [`huggingface.co`](https://www.huggingface.co)

* Ollama : [`ollama.com`](https://www.ollama.com)

* OCI : [`opencontainers.org`](https://opencontainers.org)
(quay.io, docker.io, Artifactory)

RamaLama uses the OCI registry transport by default. Use the RAMALAMA_TRANSPORTS environment variable to modify the default. `export RAMALAMA_TRANSPORT=ollama` Changes RamaLama to use ollama transport.

Individual model transports can be modifies when specifying a model via the `huggingface://`, `oci://`, or `ollama://` prefix.

ramalama pull `huggingface://`afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k.gguf

**ramalama [GLOBAL OPTIONS]**

## GLOBAL OPTIONS

#### **--dryrun**
Show container runtime command without executing it (default: False)

#### **--help**, **-h**

Show this help message and exit

#### **--nocontainer**
Do not run ramamlama in the default container (default: False)
Use environment variale "RAMALAMA_IN_CONTAINER=false" to change default.

#### **--store**=STORE

Store AI Models in the specified directory (default rootless: `$HOME/.local/share/ramalama`, default rootful: `/var/lib/ramalama`)

## COMMANDS

| Command                                          | Description                                                                 |
| ------------------------------------------------ | --------------------------------------------------------------------------- |
| [ramalama-list(1)](ramalama-list.1.md)  | List all AI models in local storage.                       |
| [ramalama-login(1)](ramalama-login.1.md)| Login to remote model registry.                            |
| [ramalama-logout(1)](ramalama-logout.1.md)| Logout from remote model registry.                       |
| [ramalama-pull(1)](ramalama-pull.1.md)  | Pull AI Models into local storage.                         |
| [ramalama-push(1)](ramalama-push.1.md)  | Push AI Model (OCI-only at present)                        |
| [ramalama-run(1)](ramalama-run.1.md)    | Run specified AI Model as a chatbot.                       |
| [ramalama-serve(1)](ramalama-serve.1.md)| Serve specified AI Model as an API server.                 |
| [ramalama-version(1)](ramalama-version.1.md)| Display the ramalama version                           |

## CONFIGURATION FILES


## SEE ALSO
**[podman(1)](https://github.com/containers/podman/blob/main/docs/podman.1.md)**

## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
