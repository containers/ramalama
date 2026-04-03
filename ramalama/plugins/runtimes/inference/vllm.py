import argparse
from http.client import HTTPConnection
from typing import Any

from ramalama.cli import suppressCompleter
from ramalama.common import ContainerEntryPoint
from ramalama.config import ActiveConfig
from ramalama.logger import logger
from ramalama.plugins.runtimes.inference.common import ContainerizedInferenceRuntimePlugin
from ramalama.transports.transport_factory import New

_VLLM_DEFAULT_IMAGE = "docker.io/vllm/vllm-openai:latest"

_VLLM_IMAGES: dict[str, str] = {
    "CUDA_VISIBLE_DEVICES": "docker.io/vllm/vllm-openai",
    "HIP_VISIBLE_DEVICES": "docker.io/vllm/vllm-openai-rocm",
    "INTEL_VISIBLE_DEVICES": "docker.io/intel/vllm",
}


class VllmPlugin(ContainerizedInferenceRuntimePlugin):
    @property
    def name(self) -> str:
        return "vllm"

    def _cmd_run(self, args: argparse.Namespace) -> list[str]:
        cmd: list[str] = []

        is_container = args.container
        should_generate = getattr(args, 'generate', None) is not None
        dry_run = getattr(args, 'dryrun', False)

        model = New(args.MODEL, args) if hasattr(args, 'MODEL') else None

        if is_container:
            cmd.append(ContainerEntryPoint())
        else:
            cmd += ["python3", "-m", "vllm.entrypoints.openai.api_server"]

        if model is not None:
            model_path = model._get_entry_model_path(is_container, should_generate, dry_run)
            cmd += ["--model", model_path]
            cmd += ["--served-model-name", model.model_alias]

        ctx_size = getattr(args, 'ctx_size', None)
        if ctx_size:
            cmd += ["--max-model-len", str(ctx_size)]

        # --host: use 0.0.0.0 in container, or the configured host otherwise
        host = '0.0.0.0' if is_container else getattr(args, 'host', None)
        if host is not None:
            cmd += ["--host", str(host)]

        port = getattr(args, 'port', None)
        if port is not None:
            cmd += ["--port", str(port)]

        seed = getattr(args, 'seed', None)
        if seed is not None:
            cmd += ["--seed", str(seed)]

        temp = getattr(args, 'temp', None)
        if temp is not None:
            cmd += ["--temperature", str(temp)]

        runtime_args = getattr(args, 'runtime_args', None)
        if runtime_args:
            cmd.extend(runtime_args)

        return cmd

    _cmd_serve = _cmd_run

    def _add_max_model_len_arg(self, parser: "argparse.ArgumentParser") -> None:
        config = ActiveConfig()
        # --ctx-size is already registered by runtime_options(); add --max-model-len as a vllm-specific alias
        parser.add_argument(
            "--max-model-len",
            dest="ctx_size",
            type=int,
            default=config.ctx_size,
            help="model context length (sequence length); alias for --ctx-size",
            completer=suppressCompleter,
        )

    def _register_run_subcommand(self, subparsers: "argparse._SubParsersAction") -> "argparse.ArgumentParser":
        parser = super()._register_run_subcommand(subparsers)
        self._add_max_model_len_arg(parser)
        return parser

    def _register_serve_subcommand(self, subparsers: "argparse._SubParsersAction") -> "argparse.ArgumentParser":
        parser = super()._register_serve_subcommand(subparsers)
        self._add_max_model_len_arg(parser)
        return parser

    def get_container_image(self, config: Any, detected_gpu_type: str) -> str | None:
        if detected_gpu_type:
            image = config.images.get(f"VLLM_{detected_gpu_type}") or _VLLM_IMAGES.get(detected_gpu_type)
            if image:
                return image

        return config.images.get("VLLM") or _VLLM_DEFAULT_IMAGE

    def service_ready_check(self, conn: HTTPConnection, args: Any, model_name: str | None = None) -> bool:
        conn.request("GET", "/ping")
        resp = conn.getresponse()
        container_name = f"container {args.name}" if getattr(args, 'container', None) else 'server'
        if resp.status != 200:
            logger.debug(f"{self.name} {container_name} /ping status code: {resp.status}: {resp.reason}")
            return False
        logger.debug(f"{self.name} {container_name} is ready")
        return True
