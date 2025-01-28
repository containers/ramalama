% ramalama-perplexity 1

## NAME
ramalama\-perplexity - calculate the perplexity value of an AI Model

## SYNOPSIS
**ramalama perplexity** [*options*] *model* [arg ...]

## MODEL TRANSPORTS

| Transports    | Prefix | Web Site                                            |
| ------------- | ------ | --------------------------------------------------- |
| URL based    | https://, http://, file:// | `https://web.site/ai.model`, `file://tmp/ai.model`|
| HuggingFace   | huggingface://, hf://, hf.co/ | [`huggingface.co`](https://www.huggingface.co)      |
| Ollama        | ollama:// | [`ollama.com`](https://www.ollama.com)              |
| OCI Container Registries | oci:// | [`opencontainers.org`](https://opencontainers.org)|
|||Examples: [`quay.io`](https://quay.io),  [`Docker Hub`](https://docker.io),[`Artifactory`](https://artifactory.com)|

RamaLama defaults to the Ollama registry transport. This default can be overridden in the `ramalama.conf` file or via the RAMALAMA_TRANSPORTS
environment. `export RAMALAMA_TRANSPORT=huggingface` Changes RamaLama to use huggingface transport.

Modify individual model transports by specifying the `huggingface://`, `oci://`, `ollama://`, `https://`, `http://`, `file://` prefix to the model.

URL support means if a model is on a web site or even on your local system, you can run it directly.

## OPTIONS

#### **--help**, **-h**
show this help message and exit

## DESCRIPTION
Calculate the perplexity of an AI Model. Perplexity measures how well the model can predict the next token with lower values being better.

## EXAMPLES

```
ramalama perplexity granite-moe3
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Jan 2025, Originally compiled by Eric Curtin <ecurtin@redhat.com>
