# ramalama

The goal of ramalama is to make AI even more boring.

## Install

Install ramalama by running this one-liner:

```
curl -fsSL https://raw.githubusercontent.com/ericcurtin/ramalama/s/install.sh | sudo bash
```

## Usage

### Running Models

You can run a model using the `run` command. This will start an interactive session where you can query the model.

```
$ ramalama run granite
> Tell me about podman in less than ten words
A fast, secure, and private container engine for modern applications.
>
```

### Serving Models

To serve a model via HTTP, use the `serve` command. This will start an HTTP server that listens for incoming requests to interact with the model.

```
$ ramalama serve granite
...
{"tid":"140477699799168","timestamp":1719579518,"level":"INFO","function":"main","line":3793,"msg":"HTTP server listening","n_threads_http":"11","port":"8080","hostname":"127.0.0.1"}
...
```

## Model library

| Model              | Parameters | Run                            |
| ------------------ | ---------- | ------------------------------ |
| granite            | 3B         | `ramalama run granite`         |
| mistral            | 7B         | `ramalama run mistral`         |
| merlinite          | 7B         | `ramalama run merlinite`       |

## Diagram

```
+----------------+
|                |
| ramalama run   |
|                |
+-------+--------+
        |
        v
+----------------+    +-----------------------+    +------------------+
|                |    | Pull runtime layer    |    | Pull model layer |
| Auto-detect    +--->| for llama.cpp         +--->| i.e. granite     |
| hardware type  |    | (CPU, Vulkan, AMD,    |    |                  |
|                |    |  Nvidia, Intel,       |    +------------------+
+----------------+    |  Apple Silicon, etc.) |    | Repo options:    |
                      +-----------------------+    +-+-------+------+-+
                                                     |       |      |
                                                     v       v      v
                                             +---------+ +------+ +----------+
                                             | Hugging | | quay | | Ollama   |
                                             | Face    | |      | | Registry |
                                             +-------+-+ +---+--+ +-+--------+
                                                     |       |      |
                                                     v       v      v
                                                   +------------------+
                                                   | Start container  |
                                                   | with llama.cpp   |
                                                   | and granite      |
                                                   | model            |
                                                   +------------------+
```

## In development

Regard this alpha, everything is under development, so expect breaking changes, luckily it's easy to reset everything and re-install:

```
rm -rf /var/lib/ramalama/storage # only required if running as root user
rm -rf $HOME/.local/share/ramalama/storage
```

and install again.

## Credit where credit is due

For the vast majority of AI/LLM software we use, under the covers the heavy lifting is being done by:

https://github.com/ggerganov/llama.cpp

so if you like this tool, give llama.cpp repo a :star:, and hey, give us a :star: too while you are at it.

