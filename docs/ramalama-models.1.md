% ramalama-models 1

## NAME
ramalama\-models - list models served by a running inference server

## SYNOPSIS
**ramalama models** [*options*]

## DESCRIPTION
List model identifiers exposed by a running inference server, such as one started
with **ramalama serve**. The command queries the server's OpenAI-compatible
**/v1/models** endpoint first (works with llama.cpp, MLX, and other OpenAI-compatible
servers), then falls back to the llama.cpp native **/models** endpoint.

This differs from **ramalama list**, which shows models downloaded to local
storage.

## OPTIONS

#### **--api-key**
OpenAI-compatible API key.
Can also be set in ramalama.conf or via the RAMALAMA_API_KEY environment variable.

#### **--help**, **-h**
show this help message and exit

#### **--json**
print model list in json format

#### **--url**=URL
model server URL (default: http://127.0.0.1:8080)

## EXAMPLES

List models served on the default local endpoint
```console
$ ramalama models
tinyllama
```

List models from a specific server in JSON format
```console
$ ramalama models --url http://localhost:1234 --json
["granite3-moe", "tinyllama"]
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-serve(1)](ramalama-serve.1.md)**, **[ramalama-list(1)](ramalama-list.1.md)**

## HISTORY
Jul 2026, Originally compiled by Dan Walsh <dwalsh@redhat.com>
