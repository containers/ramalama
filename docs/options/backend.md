####> This option file is used in:
####>   ramalama bench, ramalama perplexity, ramalama run, ramalama sandbox goose, ramalama sandbox opencode, ramalama serve
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--backend**=*auto* | vulkan | rocm | cuda | sycl | openvino | cann | musa

GPU backend to use for inference (default: auto).

Available backends depend on the detected GPU hardware.

**auto** (default): Automatically selects the preferred backend based on your GPU:
- **AMD GPUs**: vulkan (Linux/macOS) or rocm (Windows)
- **NVIDIA GPUs**: cuda
- **Intel GPUs**: vulkan (Linux/macOS) or sycl (Windows); openvino available as explicit option
- **Ascend NPUs**: cann
- **MUSA GPUs**: musa
- **No GPU**: vulkan (CPU fallback)

**Platform-specific behavior**:
- On **Linux/macOS**, Vulkan provides broad compatibility and is preferred for AMD and Intel GPUs
- On **Windows**, vulkan is not supported on WSL2, so vendor-specific backends (rocm, sycl) are preferred

**Explicit backend selection**:
- **vulkan**: Use Vulkan-based inference (compatible with AMD, Intel, and CPU)
- **rocm**: Use AMD ROCm backend (AMD GPUs only)
- **cuda**: Use NVIDIA CUDA backend (NVIDIA GPUs only)
- **sycl**: Use Intel SYCL/oneAPI backend (Intel GPUs only)
- **openvino**: Use Intel OpenVINO backend (Intel GPUs only); uses `quay.io/ramalama/openvino`
- **cann**: Use Huawei CANN backend (Ascend NPUs only); uses `quay.io/ramalama/cann`
- **musa**: Use Moore Threads MUSA backend (MUSA GPUs only); uses `quay.io/ramalama/musa`

**Available choices**: The allowed values for `--backend` are dynamically determined based on
your detected GPU hardware. For example, on a system with an AMD GPU, only `auto`, `vulkan`,
and `rocm` are available.

**Configuration**: The default can be overridden in the `ramalama.conf` file or via the
RAMALAMA_BACKEND environment variable.

Examples:
```
# Use auto-detection (default)
ramalama <<fullsubcommand>> granite

# Force Vulkan backend
ramalama <<fullsubcommand>> --backend vulkan granite

# Force ROCm backend on AMD GPU
ramalama <<fullsubcommand>> --backend rocm granite
```
