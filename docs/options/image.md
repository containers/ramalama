####> This option file is used in:
####>   ramalama bench, ramalama perplexity, ramalama run, ramalama sandbox goose, ramalama sandbox opencode, ramalama serve
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--image**=IMAGE
OCI container image to run with specified AI model. RamaLama defaults to using
images based on the accelerator it discovers and the selected `--backend`.
For example: `quay.io/ramalama/ramalama`. See the table below for all default images.
The default image tag is based on the minor version of the RamaLama package.
Version 0.18.0 of RamaLama pulls an image with a `:0.18` tag from the quay.io/ramalama OCI repository. The --image option overrides this default.

The default can be overridden in the `ramalama.conf` file or via the
RAMALAMA_IMAGE environment variable. `export RAMALAMA_IMAGE=quay.io/ramalama/aiimage:1.2` tells
RamaLama to use the `quay.io/ramalama/aiimage:1.2` image.

**Note**: The `--backend` option provides a higher-level way to select the appropriate image
based on GPU type. Use `--backend` to select vulkan, rocm, cuda, sycl, or openvino backends, which will
automatically choose the correct image. Use `--image` only when you need to override the image
selection entirely.

Accelerated images:

| Backend / Accelerator   | Image                      |
| ------------------------| -------------------------- |
|  CPU, Vulkan            | quay.io/ramalama/ramalama  |
|  ROCm (AMD)             | quay.io/ramalama/rocm      |
|  CUDA (NVIDIA)          | quay.io/ramalama/cuda      |
|  Intel GPU (sycl)       | quay.io/ramalama/intel-gpu |
|  Intel GPU (openvino)   | ghcr.io/ggml-org/llama.cpp:full-openvino |
|  Asahi (Apple Silicon)  | quay.io/ramalama/asahi     |
|  CANN (Ascend)          | quay.io/ramalama/cann      |
|  MUSA (Moore Threads)   | quay.io/ramalama/musa      |

Upstream llama.cpp "full" images from `ghcr.io/ggml-org/llama.cpp` are also supported.
RamaLama automatically detects the image type and adjusts the container CLI accordingly.

```
ramalama <<fullsubcommand>> --image ghcr.io/ggml-org/llama.cpp:full-vulkan MODEL
```
