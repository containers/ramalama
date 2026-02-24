import argparse
import platform
import time

from ramalama.logger import logger
from ramalama.plugins.runtimes.common import BaseInferenceRuntime


class MlxPlugin(BaseInferenceRuntime):
    @property
    def name(self) -> str:
        return "mlx"

    def _cmd_run(self, args: argparse.Namespace) -> list[str]:
        from ramalama.transports.transport_factory import New

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

    def setup_args(self, args: argparse.Namespace) -> None:
        if getattr(args, "container", None) is True:
            logger.info("MLX runtime automatically uses --nocontainer mode")
        args.container = False

    def validate_args(self, args) -> None:
        is_apple_silicon = platform.system() == "Darwin" and platform.machine() == "arm64"
        if not is_apple_silicon:
            raise ValueError("MLX runtime is only supported on macOS with Apple Silicon.")

    def chat_prefix(self) -> str | None:
        return "🍏 > "

    def handle_nocontainer_chat(self, args, transport) -> int | None:
        from typing import cast

        from ramalama import chat
        from ramalama.arg_types import ChatArgsType
        from ramalama.common import perror

        args.ignore = getattr(args, "dryrun", False)
        args.initial_connection = True
        max_retries = 10

        for i in range(max_retries):
            try:
                if transport._is_server_ready(args.port):
                    args.initial_connection = False
                    time.sleep(1)  # Give server time to stabilize
                    chat.chat(cast(ChatArgsType, args))
                    break
                else:
                    logger.debug(f"MLX server not ready, waiting... (attempt {i + 1}/{max_retries})")
                    time.sleep(3)
                    continue

            except Exception as e:
                if i >= max_retries - 1:
                    perror(f"Error: Failed to connect to MLX server after {max_retries} attempts: {e}")
                    transport._cleanup_server_process(args.server_process)
                    raise e
                logger.debug(f"Connection attempt failed, retrying... (attempt {i + 1}/{max_retries}): {e}")
                time.sleep(3)

        args.initial_connection = False
        return 0

    def api_model_name(self, args) -> str | None:
        return None
