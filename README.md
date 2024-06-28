# podman-llm

The goal of podman-llm is to make AI even more boring.

## Install

Install podman-llm by running this one-liner:

```bash
curl -fsSL https://raw.githubusercontent.com/ericcurtin/podman-llm/main/install.sh | sudo bash
```

## Usage

``` bash
$ podman-llm run granite
> Tell me about podman in less than ten words
 A fast, secure, and private container engine for modern applications.
>
```

``` bash
$ podman-llm serve granite
...
{"tid":"140477699799168","timestamp":1719579518,"level":"INFO","function":"main","line":3793,"msg":"HTTP server listening","n_threads_http":"11","port":"8080","hostname":"127.0.0.1"}
...
```

