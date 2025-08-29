# RamaLama

This script demonstrates running RamaLama with a sample workflow that pulls a model, serves it, and allows testing inference through a browser or curl.

## Requirements

- [RamaLama](https://github.com/) installed and available in your PATH  
- [Podman](https://podman.io/) installed and configured  

## Usage

Run the script:

```bash
./ramalama.sh
````

Override the browser (optional):

```bash
BROWSER=google-chrome ./ramalama.sh
```

## Features

* Pulls and runs the `smollm:135m` and `granite` models with RamaLama
* Opens the service endpoint in your browser automatically
* Waits for the service to be ready before testing inference
* Performs a sample inference with `curl` against the `granite3.1-dense` model

## Advanced usage

You can also call specific functions from the script directly, for example:

```bash
./ramalama.sh pull
./ramalama.sh run
./ramalama.sh test
```

Extra arguments can be passed after the function name if supported.

---
