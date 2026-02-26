# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RamaLama is a CLI tool for managing and serving AI models using containers. It provides a container-centric approach to AI model management, supporting multiple model registries (Hugging Face, Ollama, OCI registries) and automatic GPU detection with appropriate container image selection.

## Build and Development Commands

### Setup
```bash
make install-requirements    # Install dev dependencies via pip
```

### Testing
```bash
# Unit tests (pytest via tox)
make unit-tests              # Run unit tests
make unit-tests-verbose      # Run with full trace output
tox                          # Direct tox invocation

# E2E tests (pytest)
make e2e-tests               # Run with Podman (default)
make e2e-tests-docker        # Run with Docker
make e2e-tests-nocontainer   # Run without container engine

# System tests (BATS)
make bats                    # Run BATS system tests
make bats-nocontainer        # Run in nocontainer mode
make bats-docker             # Run with Docker

# All tests
make tests                   # Run unit tests and system-level integration tests
```

### Running a single test
```bash
# Unit test
tox -- test/unit/test_cli.py::test_function_name -vvv

# E2E test
tox -e e2e -- test/e2e/test_basic.py::test_function_name -vvv

# Single BATS file
RAMALAMA=$(pwd)/bin/ramalama bats -T test/system/030-run.bats
```

### Code Quality
```bash
make validate                # Run all validation (codespell, lint, format check, man-check, type check)
make lint                    # Run ruff + shellcheck
make check-format            # Check ruff formatting + import sorting
make format                  # Auto-format with ruff + import sorting
make type-check              # Run mypy type checking
make codespell               # Check spelling
```

### Documentation
```bash
make docs                    # Build manpages and docsite
```

## Architecture

### Source Structure (`ramalama/`)
- `cli.py` - Main CLI entry point, argparse setup, subcommand dispatch
- `config.py` - Configuration constants and loading
- `common.py` - Shared utility functions, GPU detection (`get_accel()`)
- `engine.py` - Container engine abstraction (Podman/Docker)

### Transport System (`ramalama/transports/`)
Handles pulling/pushing models from different registries:
- `base.py` - Base `Transport` class defining the interface
- `transport_factory.py` - `New()` and `TransportFactory` for creating transports
- `huggingface.py`, `ollama.py`, `oci.py`, `modelscope.py`, `rlcr.py` - Registry-specific implementations
- Transports are selected via URL scheme prefixes: `huggingface://`, `ollama://`, `oci://`, etc.

### Model Store (`ramalama/model_store/`)
Manages local model storage:
- `global_store.py` - `GlobalModelStore` for model management
- `store.py` - Low-level storage operations
- `reffile.py` - Reference file handling for tracking model origins

### Runtime Plugin System (`ramalama/plugins/`)
Each inference engine is a self-contained Python plugin:
- `interface.py` - Abstract base classes: `RuntimePlugin` and `InferenceRuntimePlugin`
- `loader.py` - Plugin discovery and `get_all_runtimes()` / `get_runtime()`; entry point group `ramalama.runtimes.v1alpha`
- `registry.py` - Plugin registration
- `runtimes/inference/common.py` - Concrete base classes:
  - `BaseInferenceRuntime` — registers `run` and `serve`, implements `handle_subcommand()` dispatch
  - `ContainerizedInferenceRuntimePlugin` — extends the above with container-specific args (`--api`, `--generate`)
- `runtimes/inference/llama_cpp.py` - `LlamaCppPlugin(LlamaCppCommands, ContainerizedInferenceRuntimePlugin)` (default); owns all RAG subcommand logic
- `runtimes/inference/llama_cpp_commands.py` - `LlamaCppCommands` mixin providing `_cmd_run`, `_cmd_serve`, and other llama.cpp command builders
- `runtimes/inference/vllm.py` - `VllmPlugin(ContainerizedInferenceRuntimePlugin)`
- `runtimes/inference/mlx.py` - `MlxPlugin(BaseInferenceRuntime)` (macOS only; always --nocontainer)

`configure_subcommands()` in `cli.py` calls `register_subcommands()` on only the
selected runtime plugin, so `--help` output is filtered to the active runtime's
supported subcommands.

### Key Patterns
- **GPU Detection**: `get_accel()` in `common.py` detects GPU type (CUDA, ROCm, Vulkan, etc.) and selects appropriate container image
- **Container Images**: GPU-specific images at `quay.io/ramalama/{ramalama,cuda,rocm,intel-gpu,...}`
- **Inference Engines**: llama.cpp (default), vllm, mlx (macOS only) - each implemented as a runtime plugin under `ramalama/plugins/runtimes/inference/`

## Test Structure

- `test/unit/` - pytest unit tests (fast, no external dependencies)
- `test/e2e/` - pytest end-to-end tests (marked with `@pytest.mark.e2e`)
- `test/system/` - BATS shell tests for full CLI integration testing

## Code Style

- Python 3.10+ required
- Line length: 120 characters
- Formatting: ruff format + ruff check (I rules)
- Type hints encouraged (mypy checked)
- Commits require DCO sign-off (`git commit -s`)
