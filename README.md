# podman-llm

The goal of podman-llm is to make AI even more boring.

## Install

Install podman-llm by running this one-liner:

```
curl -fsSL https://raw.githubusercontent.com/ericcurtin/podman-llm/main/install.sh | sudo bash
```

## Usage

### Running Models

You can run a model using the `run` command. This will start an interactive session where you can query the model.

```
$ podman-llm run granite
> Tell me about podman in less than ten words
A fast, secure, and private container engine for modern applications.
>
```

### Serving Models

To serve a model via HTTP, use the `serve` command. This will start an HTTP server that listens for incoming requests to interact with the model.

```
$ podman-llm serve granite
...
{"tid":"140477699799168","timestamp":1719579518,"level":"INFO","function":"main","line":3793,"msg":"HTTP server listening","n_threads_http":"11","port":"8080","hostname":"127.0.0.1"}
...
```

## Model library

| Model              | Parameters | Run                            |
| ------------------ | ---------- | ------------------------------ |
| granite            | 3B         | `podman-llm run granite`       |
| mistral            | 7B         | `podman-llm run mistral`       |
| merlinite          | 7B         | `podman-llm run merlinite`     |

## Containerfile Example

Here is an example Containerfile:

```
FROM quay.io/podman-llm/podman-llm:41
RUN llama-main --hf-repo ibm-granite/granite-3b-code-instruct-GGUF -m granite-3b-code-instruct.Q4_K_M.gguf
LABEL MODEL=/granite-3b-code-instruct.Q4_K_M.gguf
```

`LABEL MODEL` is important so we know where to find the .gguf file.

And we build via:

```
podman build -t granite podman-llm/granite:3b
```

## Diagram

```
+------------------------+    +--------------------+    +------------------+
|                        |    | Pull runtime layer |    | Pull model layer |
|    podman-llm run      | -> | with llama.cpp     | -> | with granite     |
|                        |    |                    |    |                  |
+------------------------+    +--------------------+    |------------------|
                                                        | Repo options:    |
                                                        +------------------+
                                                            |          |
                                                            v          v
                                                    +--------------+ +---------+
                                                    | Hugging Face | | quay.io |
                                                    +--------------+ +---------+
                                                            \          /
                                                             \        /
                                                              \      /
                                                               v    v
                                                        +-----------------+
                                                        | Start container |
                                                        | with llama.cpp  |
                                                        | and granite     |
                                                        | model           |
                                                        +-----------------+
```

