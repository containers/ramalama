# podman-llm

The goal of podman-llm is to make AI even more boring.

## Install

Install podman-llm by running this one-liner:

```bash
curl -fsSL https://raw.githubusercontent.com/ericcurtin/podman-llm/main/install.sh | sudo bash
```

## Usage

### Running Models

You can run a model using the `run` command. This will start an interactive session where you can query the model.

```bash
$ podman-llm run granite
> Tell me about podman in less than ten words
A fast, secure, and private container engine for modern applications.
>
```

### Serving Models

To serve a model via HTTP, use the `serve` command. This will start an HTTP server that listens for incoming requests to interact with the model.

```bash
$ podman-llm serve granite
...
{"tid":"140477699799168","timestamp":1719579518,"level":"INFO","function":"main","line":3793,"msg":"HTTP server listening","n_threads_http":"11","port":"8080","hostname":"127.0.0.1"}
...
```

