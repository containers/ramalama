from __future__ import annotations

import argparse
import platform
from dataclasses import dataclass
from http.client import HTTPConnection
from typing import Any, Optional

from ramalama.cli import suppressCompleter
from ramalama.config import ActiveConfig
from ramalama.logger import logger
from ramalama.plugins.runtimes.inference.common import BaseInferenceRuntime
from ramalama.transports.transport_factory import New


@dataclass
class MlxConfig:
    temp: float = 0.8

    def __post_init__(self):
        self.temp = float(self.temp)


class MlxPlugin(BaseInferenceRuntime):
    config_type = MlxConfig

    @property
    def name(self) -> str:
        return "mlx"

    def _add_inference_args(self, parser: "argparse.ArgumentParser", command: str) -> None:
        super()._add_inference_args(parser, command)
        rt_config = self.get_runtime_config(ActiveConfig())
        parser.add_argument(
            "--temp",
            dest="temp",
            type=float,
            default=rt_config.temp,
            help="temperature of the response from the AI model",
            completer=suppressCompleter,
        )

    def _cmd_run(self, args: argparse.Namespace) -> list[str]:
        cmd = ["mlx_lm.server"]

        is_container = args.container
        should_generate = getattr(args, 'generate', None) is not None
        dry_run = getattr(args, 'dryrun', False)

        model = New(args.MODEL, args) if hasattr(args, 'MODEL') else None

        if model is not None:
            model_path = model._get_entry_model_path(is_container, should_generate, dry_run)
            cmd += ["--model", model_path]

        temp = getattr(args, 'temp', None)
        if temp is not None:
            cmd += ["--temp", str(temp)]

        seed = getattr(args, 'seed', None)
        if seed is not None:
            cmd += ["--seed", str(seed)]

        max_tokens = getattr(args, 'max_tokens', None)
        max_tokens = max_tokens if max_tokens else 0
        if max_tokens > 0:
            cmd += ["--max-tokens", str(max_tokens)]

        host = getattr(args, 'host', None)
        if host is not None:
            cmd += ["--host", str(host)]

        port = getattr(args, 'port', None)
        if port is not None:
            cmd += ["--port", str(port)]

        runtime_args = getattr(args, 'runtime_args', None)
        if runtime_args:
            cmd.extend(runtime_args)

        return cmd

    _cmd_serve = _cmd_run

    def post_process_args(self, args: argparse.Namespace) -> None:
        is_apple_silicon = platform.system() == "Darwin" and platform.machine() == "arm64"
        if not is_apple_silicon:
            raise ValueError("MLX runtime is only supported on macOS with Apple Silicon.")
        if getattr(args, "container", None) is True:
            logger.info("MLX runtime automatically uses --nocontainer mode")
        args.container = False

    def service_ready_check(self, conn: HTTPConnection, args: Any, model_name: Optional[str] = None) -> bool:
        conn.request("GET", "/health")
        resp = conn.getresponse()
        if resp.status != 200:
            logger.debug(f"{self.name} server /health status code: {resp.status}: {resp.reason}")
            return False
        logger.debug(f"{self.name} server is ready")
        return True

    @property
    def chat_include_model_name(self) -> bool:
        # Do not include the model name in the request. Otherwise MLX will try to refetch it from HF
        return False
