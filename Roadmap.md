# RamaLama Roadmap

This document outlines upcoming features and initiatives for RamaLama.  
Contributors can comment on or contribute to the issues linked here.

---

## 🚀 New Commands
- `ramalama summarize`
- `ramalama audio2text`
- `ramalama prompt2img sd <model>`
- `ramalama --container-name=<name> upload <file>`
  - Upload files (image, text, PDF, etc.) to a containerized model.
  - No action initially; waits for a prompt such as “summarize this text.”

---

## 🛠️ Runtime & Design Improvements
- Make **MODEL runtimes more pluggable**  
  Define a syntax that simplifies adding new runtimes.  
  Current runtimes:  
  - `llama.cpp`  
  - `vllm`  
  - `stable-diffusion`  
  - `OpenVINO`  

- **OpenVINO integration**  
  - Coordinating with Intel for CPU/accelerator support.

- **Model OCI Artifact support**  
  - Podman 5.6: `podman-remote artifact` support.  
  - Match Docker behaviour for storing models as OCI artifacts.  
  - Reference: [CNCF sandbox issue #358](https://github.com/cncf/sandbox/issues/358).  
  - Evaluate defaulting `--container` mode to automatically convert models to OCI artifacts.

---

## 📚 Retrieval-Augmented Generation (RAG)  
- Add support for **RAG pipelines**.  
- Explore **MCP (Model Context Protocol)** integration.

---

## 🐑 Llama-stack Features
- Consolidation of images.  
- Default AMD RamaLama images to:  
  - `quay.io/ramalama/ramalama`  
- Assess Intel-specific image defaults.

---

## 🎮 Vulkan Efforts
- Expand support for Vulkan backends.  
- Ensure compatibility across GPUs.

---

## 🧩 Additional Tooling
- **VSCode Plugin**
  - Start a RamaLama container with the local project mounted.  
  - AI-assisted code analysis and suggestions (similar to GitHub Copilot).  
  - Key difference: data stays on the developer’s machine.  
  - May require MCP server integration.

- **Automated Image Detection**
  - Detect best base image from a compatibility matrix.  
  - Automatically select and execute commands with the correct image.

---
