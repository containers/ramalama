% ramalama 1

## NAME
ramalama - Simple management tool for working with AI Models

## SYNOPSIS
**ramalama** [*options*] *command*

## DESCRIPTION
Ramalama : The goal of ramalama is to make AI boring.

Ramalama supports multiple types of model registries. Currently the following types of AI Model registries (transports):

* HuggingFace : [`huggingface.co`](https://www.huggingface.co)

* Ollama : [`ollama.com`](https://www.ollama.com)

* OCI : [`opencontainers.org`](https://opencontainers.org)
(quay.io, docker.io, Artifactory)

RamaLama uses the OCI registry transport by default. Use the RAMALAMA_TRANSPORTS environment variable to modify the default.

`export RAMALAMA_TRANSPORT=ollama`

Changes RamaLama to use ollama transport.

Individual model transports can be modifies when specifying a model via the `huggingface://`, `oci://`, or `ollama://` prefix.

`ramalama pull huggingface://afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k.gguf`

**ramalama [GLOBAL OPTIONS]**

## COMMANDS

| Command                                          | Description                                                                 |
| ------------------------------------------------ | --------------------------------------------------------------------------- |
| [ramalama-list(1)](ramalama-list.1.md)  | List all AI models in local storage.                       |
| [ramalama-login(1)](ramalama-login.1.md)| Login to model registry.                                   |
| [ramalama-logout(1)](ramalama-logout.1.md)| Logout from model registry.                              |
| [ramalama-pull(1)](ramalama-pull.1.md)  | Pull AI Model from registry to local storage                |
| [ramalama-push(1)](ramalama-push.1.md)  | Push specified AI Model (OCI-only at present)               |
| [ramalama-run(1)](ramalama-run.1.md)    | Run a chatbot on AI Model.                                  |
| [ramalama-serve(1)](ramalama-serve.1.md)| Serve local AI Model as an API Service.                     |

## CONFIGURATION FILES


## SEE ALSO
**[podman(1)](https://github.com/containers/podman/blob/main/docs/podman.1.md)**)

## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
