# RamaLama Demo

This script demonstrates running RamaLama with a sample workflow that pulls a model, serves it, and allows testing inference through a browser or curl.

## Requirements

- [RamaLama](https://github.com/containers/ramalama) installed and available in your PATH
- [Podman](https://podman.io/) installed and configured

## Usage

Run the full demo (all sections including multi-modal, MCP, and RAG):

```bash
./ramalama.sh
```

Run only the multi-modal demo (after core demos):

```bash
./ramalama.sh multi-modal
```

Run only the MCP + RAG demo (after core demos):

```bash
./ramalama.sh mcp
```

Override the browser (optional):

```bash
BROWSER=google-chrome ./ramalama.sh
```

## Demo Modes

The script supports three demo modes for the final section, selectable via the first argument:

| Mode | Command | Description |
|------|---------|-------------|
| `all` (default) | `./ramalama.sh` or `./ramalama.sh all` | Runs all demos: multi-modal, MCP, and RAG |
| `multi-modal` | `./ramalama.sh multi-modal` | Serves SmolVLM and opens a camera interaction app in the browser |
| `mcp` | `./ramalama.sh mcp` | Runs MCP server tools with phi4 and a RAG demo with a vector database |

All modes share the same core demos: version, pull, run, serve (including llama-stack), kubernetes, and quadlet.

## Features

* Pulls and runs the `smollm:135m` and `granite` models
* Shows container security features (cap-drop, network isolation)
* Serves models via REST API with browser interaction
* Demonstrates llama-stack API integration
* Generates Kubernetes YAML and Quadlet files for model deployment
* Multi-modal: camera-based vision inference with SmolVLM
* MCP: tool-calling with MCP server and RAG document retrieval

## Running Individual Functions

You can run specific demo sections directly (these run only the named function, without the core demos):

```bash
./ramalama.sh version
./ramalama.sh pull
./ramalama.sh run
./ramalama.sh serve
./ramalama.sh kubernetes
./ramalama.sh quadlet
./ramalama.sh rag
```

Extra arguments can be passed after the function name if supported.

> Note: `multi-modal`, `mcp`, and `all` are demo modes (see Demo Modes above) and will run the core demos as well.
