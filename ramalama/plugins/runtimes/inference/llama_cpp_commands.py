from __future__ import annotations

import argparse
import os

from ramalama.console import should_colorize
from ramalama.transports.transport_factory import New

# llama.cpp-specific defaults — not part of global config
_NGL_DEFAULT: int = -1
_CACHE_REUSE_DEFAULT: int = 256
_THINKING_DEFAULT: bool = True


def _default_threads() -> int:
    """Compute the default number of CPU threads for llama.cpp inference."""
    nproc = os.cpu_count()
    if nproc and nproc > 4:
        return int(nproc / 2)
    return 4


class LlamaCppCommands:
    """Pure mixin providing llama.cpp command builders.

    Inherit alongside a concrete InferenceRuntimePlugin subclass::

        class LlamaCppPlugin(LlamaCppCommands, ContainerizedInferenceRuntimePlugin):
            ...

    This mixin satisfies the _cmd_run abstract method requirement and provides
    all other llama.cpp command builders.  It intentionally has no base class
    so that MRO is controlled by the plugin class itself.
    """

    def _get_model_name(self, args: argparse.Namespace) -> str:
        """Return the model name from args, checking both MODEL (CLI) and model (internal) attributes."""
        if hasattr(args, 'MODEL'):
            return New(args.MODEL, args).model_name
        model = getattr(args, 'model', None)
        if model is not None:
            return getattr(model, 'model_name', '')
        return ''

    def _cmd_run(self, args: argparse.Namespace) -> list[str]:
        if getattr(args, 'rag', None):
            return self._cmd_run_rag(args)
        cmd = ["llama-server"] if not self._container_image_is_ggml(args) else ["--server"]  # type: ignore[attr-defined]

        is_container = args.container
        should_generate = getattr(args, 'generate', None) is not None
        dry_run = getattr(args, 'dryrun', False)

        model = New(args.MODEL, args) if hasattr(args, 'MODEL') else None

        # --host: use :: in container, or the configured host otherwise
        host = '::' if is_container else getattr(args, 'host', None)
        if host is not None:
            cmd += ["--host", str(host)]

        port = getattr(args, 'port', None)
        if port is not None:
            cmd += ["--port", str(port)]

        logfile = getattr(args, 'logfile', None)
        if logfile:
            cmd += ["--log-file", str(logfile)]

        if model is not None:
            model_path = model._get_entry_model_path(is_container, should_generate, dry_run)
            cmd += ["--model", model_path]

            mmproj_path = model._get_mmproj_path(is_container, should_generate, dry_run)
            if mmproj_path:
                cmd += ["--mmproj", str(mmproj_path)]

            chat_template_path = model._get_chat_template_path(is_container, should_generate, dry_run)
            if chat_template_path:
                cmd += ["--chat-template-file", str(chat_template_path)]

        cmd.append("--no-warmup")

        if not getattr(args, 'thinking', None):
            cmd += ["--reasoning-budget", "0"]

        if model is not None:
            cmd += ["--alias", model.model_alias]

        ctx_size = getattr(args, 'ctx_size', None)
        if ctx_size and ctx_size > 0:
            cmd += ["--ctx-size", str(ctx_size)]

        temp = getattr(args, 'temp', None)
        if temp is not None:
            cmd += ["--temp", str(temp)]

        cache_reuse = getattr(args, 'cache_reuse', None)
        if cache_reuse is not None:
            cmd += ["--cache-reuse", str(cache_reuse)]

        if getattr(args, 'debug', None):
            cmd.append("-v")

        if getattr(args, 'webui', None) == 'off':
            cmd.append("--no-webui")

        ngl = getattr(args, 'ngl', 0)
        ngl_val = 999 if ngl < 0 else ngl
        cmd += ["-ngl", str(ngl_val)]

        model_draft = getattr(args, 'model_draft', None)
        if model_draft:
            draft_path = ""
            if model is not None:
                draft_model = getattr(model, 'draft_model', None)
                if draft_model:
                    draft_path = draft_model._get_entry_model_path(is_container, should_generate, dry_run)
            if draft_path:
                cmd += ["--model-draft", draft_path]
            cmd += ["-ngld", str(ngl_val)]

        threads = getattr(args, 'threads', None)
        if threads is not None:
            cmd += ["--threads", str(threads)]

        seed = getattr(args, 'seed', None)
        if seed is not None:
            cmd += ["--seed", str(seed)]

        if should_colorize():
            cmd += ["--log-colors", "on"]

        rpc_nodes = os.getenv("RAMALAMA_LLAMACPP_RPC_NODES", None)
        if rpc_nodes:
            cmd += ["--rpc", str(rpc_nodes)]

        max_tokens = getattr(args, 'max_tokens', None)
        if max_tokens and max_tokens > 0:
            cmd += ["-n", str(max_tokens)]

        runtime_args = getattr(args, 'runtime_args', None)
        if runtime_args:
            cmd.extend(runtime_args)

        return cmd

    _cmd_serve = _cmd_run

    def _cmd_perplexity(self, args: argparse.Namespace) -> list[str]:
        cmd = ["llama-perplexity"] if not self._container_image_is_ggml(args) else ["--perplexity"]  # type: ignore[attr-defined]

        is_container = args.container
        should_generate = getattr(args, 'generate', None) is not None
        dry_run = getattr(args, 'dryrun', False)

        model = New(args.MODEL, args) if hasattr(args, 'MODEL') else None

        if model is not None:
            model_path = model._get_entry_model_path(is_container, should_generate, dry_run)
            cmd += ["--model", model_path]

        ngl = getattr(args, 'ngl', 0)
        ngl_val = 999 if ngl < 0 else ngl
        cmd += ["-ngl", str(ngl_val)]

        model_draft = getattr(args, 'model_draft', None)
        if model_draft:
            cmd += ["-ngld", str(ngl_val)]

        threads = getattr(args, 'threads', None)
        if threads is not None:
            cmd += ["--threads", str(threads)]

        return cmd

    def _cmd_bench(self, args: argparse.Namespace) -> list[str]:
        cmd = ["llama-bench"] if not self._container_image_is_ggml(args) else ["--bench"]  # type: ignore[attr-defined]

        is_container = args.container
        should_generate = getattr(args, 'generate', None) is not None
        dry_run = getattr(args, 'dryrun', False)

        model = New(args.MODEL, args) if hasattr(args, 'MODEL') else None

        if model is not None:
            model_path = model._get_entry_model_path(is_container, should_generate, dry_run)
            cmd += ["--model", model_path]

        ngl = getattr(args, 'ngl', 0)
        ngl_val = 999 if ngl < 0 else ngl
        cmd += ["-ngl", str(ngl_val)]

        model_draft = getattr(args, 'model_draft', None)
        if model_draft:
            cmd += ["-ngld", str(ngl_val)]

        threads = getattr(args, 'threads', None)
        if threads is not None:
            cmd += ["--threads", str(threads)]

        cmd += ["-o", "json"]

        runtime_args = getattr(args, 'runtime_args', None)
        if runtime_args:
            cmd.extend(runtime_args)

        return cmd

    def _cmd_rag(self, args: argparse.Namespace) -> list[str]:
        cmd = ["doc2rag"]

        if getattr(args, 'debug', None):
            cmd.append("--debug")

        api_url = getattr(args, 'api_url', None)
        if api_url:
            cmd += ["--api-url", str(api_url)]

        embed_url = getattr(args, 'embed_url', None)
        if not embed_url:
            raise ValueError("--embed-url is required for RAG document processing")
        cmd += ["--embed-url", str(embed_url)]

        embed_model = getattr(args, 'embed_model', None)
        if embed_model:
            cmd += ["--embed-model", str(embed_model)]

        chunk_size = getattr(args, 'chunk_size', None)
        if chunk_size:
            cmd += ["--chunk-size", str(chunk_size)]

        ctx_size = getattr(args, 'ctx_size', None)
        if ctx_size:
            cmd += ["--ctx-size", str(ctx_size)]

        caption_url = getattr(args, 'caption_url', None)
        if caption_url:
            cmd += ["--caption-url", str(caption_url)]

        cmd.append("/output")

        if getattr(args, 'PATHS', None) and getattr(args, 'inputdir', None):
            cmd.append(str(args.inputdir))

        if getattr(args, 'urls', None):
            cmd.extend(args.urls)

        return cmd

    def _cmd_run_rag(self, args: argparse.Namespace) -> list[str]:
        cmd = ["rag_framework"]

        if getattr(args, 'debug', None):
            cmd.append("--debug")

        cmd.append("serve")

        port = getattr(args, 'port', None)
        if port is not None:
            cmd += ["--port", str(port)]

        model_host = getattr(args, 'model_host', None)
        if model_host is not None:
            cmd += ["--model-host", str(model_host)]

        model_port = getattr(args, 'model_port', None)
        if model_port is not None:
            cmd += ["--model-port", str(model_port)]

        embed_url = getattr(args, 'embed_url', None)
        if not embed_url:
            raise ValueError("--embed-url is required for RAG serving")
        cmd += ["--embed-url", str(embed_url)]

        cmd.append("/rag/vector.db")

        return cmd

    def _cmd_convert(self, args: argparse.Namespace) -> list[str]:
        cmd = ["convert_hf_to_gguf.py"] if not self._container_image_is_ggml(args) else ["--convert"]  # type: ignore[attr-defined]
        model_name = self._get_model_name(args)
        cmd += ["--outfile", f"/output/{model_name}.gguf", "/model"]
        return cmd

    def _cmd_quantize(self, args: argparse.Namespace) -> list[str]:
        cmd = ["llama-quantize"] if not self._container_image_is_ggml(args) else ["--quantize"]  # type: ignore[attr-defined]
        model_name = self._get_model_name(args)
        gguf = getattr(args, 'gguf', None) or ""
        cmd += [f"/model/{model_name}.gguf", f"/model/{model_name}-{gguf}.gguf", str(gguf)]
        return cmd
