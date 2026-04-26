from __future__ import annotations

import argparse
import json
import os
import platform
import tempfile
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, Optional, cast

from ramalama.arg_types import BaseEngineArgsType
from ramalama.common import run_cmd
from ramalama.config import ActiveConfig
from ramalama.engine import Engine, inspect, logs, stop_container, wait_for_healthy
from ramalama.plugins.loader import get_runtime
from ramalama.transports.base import compute_serving_port
from ramalama.transports.transport_factory import New


def _add_common_sandbox_args(parser: argparse.ArgumentParser) -> None:
    """Add --workdir and ARGS arguments shared by all sandbox subcommands."""
    parser.add_argument(
        "-w",
        "--workdir",
        help="local directory to mount into the sandbox container at /work",
    )
    parser.add_argument(
        "ARGS",
        nargs="*",
        help="instructions for the sandbox to process non-interactively",
    )


def add_sandbox_subparsers(subparsers: argparse._SubParsersAction, img_comp: Callable, model_comp: Callable):
    """
    Add subparsers to the provided "subparser" object for each subcommand of
    "ramalama sandbox".
    "img_comp" and "model_comp" are completer functions for images and models, respectively.
    "func" is the function that will be called when the subcommand is run.
    """
    runtime = get_runtime(ActiveConfig().runtime)
    parser = subparsers.add_parser("goose", help="run Goose in a sandbox, backed by a local AI Model")
    if getattr(runtime, "_add_inference_args", None):
        # Consider adding this to the plugin interface for commands which need to run an
        # inference server
        runtime._add_inference_args(parser, "serve")  # type: ignore[attr-defined]
    parser.add_argument("MODEL", completer=model_comp)
    parser.add_argument(
        "--goose-image",
        default="ghcr.io/block/goose:1.28.0",
        completer=img_comp,
        help="Goose container image",
    )
    _add_common_sandbox_args(parser)
    parser.set_defaults(func=run_sandbox_goose)
    yield parser

    parser = subparsers.add_parser("opencode", help="run OpenCode in a sandbox, backed by a local AI Model")
    if getattr(runtime, "_add_inference_args", None):
        runtime._add_inference_args(parser, "serve")  # type: ignore[attr-defined]
    parser.add_argument("MODEL", completer=model_comp)
    parser.add_argument(
        "--opencode-image",
        default="ghcr.io/anomalyco/opencode:1.3.7",
        completer=img_comp,
        help="OpenCode container image",
    )
    _add_common_sandbox_args(parser)
    parser.set_defaults(func=run_sandbox_opencode)
    yield parser

    parser = subparsers.add_parser("openclaw", help="run OpenClaw in a sandbox, backed by a local AI Model")
    if getattr(runtime, "_add_inference_args", None):
        runtime._add_inference_args(parser, "serve")  # type: ignore[attr-defined]
    parser.add_argument("MODEL", completer=model_comp)
    parser.add_argument(
        "--openclaw-image",
        default="ghcr.io/openclaw/openclaw:2026.4.5",
        completer=img_comp,
        help="OpenClaw container image",
    )
    parser.add_argument(
        "--openclaw-port",
        type=int,
        default=18789,
        help="OpenClaw gateway port (default: 18789)",
    )
    parser.add_argument(
        "--state-dir",
        help="local directory to mount into the OpenClaw gateway container for persistent state",
    )
    _add_common_sandbox_args(parser)
    parser.set_defaults(func=run_sandbox_openclaw)
    yield parser


class SandboxEngineArgsType(BaseEngineArgsType):
    ARGS: list[str]
    workdir: Optional[str]


class SandboxEngine(Engine):
    """Engine for running sandbox containers."""

    def __init__(self, args: SandboxEngineArgsType, *, background: bool = False) -> None:
        self.background = background
        super().__init__(args)

    def base_args(self) -> None:
        super().base_args()
        if self.background:
            self.add_args("-d")
        else:
            self.add_args("-i")

    def is_tty_cmd(self) -> bool:
        if self.background:
            return False
        return getattr(self.args, "subcommand", "") == "sandbox"

    def add_network(self) -> None:
        self.add_args(f"--network=container:{self.args.name}")  # type: ignore[attr-defined]

    def add_workdir(self, args: SandboxEngineArgsType):
        if args.workdir:
            self.add_volume(args.workdir, "/work", opts="rw")
            self.add_args("--workdir=/work")

    def add_port_option(self) -> None:
        pass

    def add_oci_runtime(self) -> None:
        pass

    def add_detach_option(self) -> None:
        pass

    def add_device_options(self) -> None:
        pass


class GooseArgsType(SandboxEngineArgsType):
    goose_image: str


class Agent:
    """
    Run an agent in a container.
    """

    def __init__(self, args: SandboxEngineArgsType, model_name: str):
        self.engine = SandboxEngine(args)
        self.model_name = model_name

    def dryrun(self) -> None:
        self.engine.dryrun()

    def run(self) -> None:
        run_cmd(self.engine.exec_args, stdout=None, stdin=None)


class Goose(Agent):
    """
    Run Goose in a sandbox.
    Environment variables required by Goose will be set, and any workdir specified will be mounted into the container.
    If args are provided, they will be passed to Goose to process non-interactively. If there are no arguments and stdin
    is a tty, an interactive session will be started. Otherwise, instructions will be read from stdin.
    """

    def __init__(self, args: GooseArgsType, model_name: str) -> None:
        super().__init__(args, model_name)
        if self.engine.use_podman:
            if platform.system() != "Windows":
                self.engine.add_args("--uidmap=+1000:0")
        self.engine.add_name(f"goose-{args.name}")  # type: ignore[attr-defined]
        self.add_env_options(args)
        self.engine.add_workdir(args)
        self.engine.add_args(args.goose_image)
        if args.ARGS:
            self.engine.add_args("run", "-t", " ".join(args.ARGS))
        elif self.engine.use_tty():
            self.engine.add_args("session")
        else:
            self.engine.add_args("run", "-i", "-")

    def add_env_options(self, args: GooseArgsType) -> None:
        self.engine.add_env_option("GOOSE_PROVIDER=openai")
        self.engine.add_env_option(f"OPENAI_HOST=http://localhost:{args.port}")
        self.engine.add_env_option("OPENAI_API_KEY=ramalama")
        self.engine.add_env_option(f"GOOSE_MODEL={self.model_name}")
        self.engine.add_env_option("GOOSE_TELEMETRY_ENABLED=false")
        self.engine.add_env_option("GOOSE_CLI_SHOW_THINKING=true")


class OpenCodeArgsType(SandboxEngineArgsType):
    opencode_image: str


class OpenCode(Agent):
    """
    Run OpenCode in a sandbox.
    Environment variables required by OpenCode will be set, and any workdir specified will be mounted into the
    container. If args are provided, they will be passed to OpenCode to process non-interactively. If there are
    no arguments and stdin is a tty, an interactive TUI session will be started. Otherwise, instructions will be
    read from stdin.
    """

    def __init__(self, args: OpenCodeArgsType, model_name: str) -> None:
        super().__init__(args, model_name)
        self.engine.add_name(f"opencode-{args.name}")  # type: ignore[attr-defined]
        self.add_env_options(args)
        self.engine.add_workdir(args)
        self.engine.add_args(args.opencode_image)
        if args.ARGS or not self.engine.use_tty():
            # Use the "run" command to process args from the command-line or stdin non-interatively
            self.engine.add_args("run", "--thinking=true")
            self.engine.add(args.ARGS)
        # Running on a tty with no arguments will start the TUI for an interactive session

    def add_env_options(self, args: OpenCodeArgsType) -> None:
        config = {
            "$schema": "https://opencode.ai/config.json",
            "model": f"ramalama/{self.model_name}",
            "provider": {
                "ramalama": {
                    "npm": "@ai-sdk/openai-compatible",
                    "name": "RamaLama",
                    "options": {
                        "baseURL": f"http://localhost:{args.port}/v1",
                        "apiKey": "ramalama",
                    },
                    "models": {
                        self.model_name: {
                            "name": self.model_name,
                        },
                    },
                },
            },
        }
        self.engine.add_env_option(f"OPENCODE_CONFIG_CONTENT={json.dumps(config)}")


class OpenClawArgsType(SandboxEngineArgsType):
    openclaw_image: str
    openclaw_port: int
    state_dir: str | None
    debug: bool


class OpenClaw(Agent):
    """
    Run OpenClaw in a sandbox using a gateway+client architecture.
    A gateway container runs in the background, configured to communicate with the local model
    server. A client container runs the TUI or agent, connecting to the gateway via websocket.
    A JSON config file is written to a temporary file and mounted into both containers via
    OPENCLAW_CONFIG_PATH.
    """

    def __init__(self, args: OpenClawArgsType, model_name: str) -> None:
        super().__init__(args, model_name)
        self.args = args
        self.config_file_path = self._write_config(args)
        self._gateway_name = f"openclaw-gateway-{args.name}"  # type: ignore[attr-defined]
        self._gateway_started = False

        #  Gateway Engine (detached background container)
        self.gateway_engine = SandboxEngine(args, background=True)
        self.gateway_engine.add_name(self._gateway_name)
        self._add_env_to_engine(self.gateway_engine, args)
        self._add_state_dir_to_engine(self.gateway_engine, args)
        self.gateway_engine.add_workdir(args)
        self.gateway_engine.add_volume(self.config_file_path, "/etc/openclaw/ramalama.json")
        self.gateway_engine.add_args(args.openclaw_image)
        self.gateway_engine.add_args("openclaw", "gateway", "run")

        # Client Engine (foreground interactive container)
        self.engine.add_name(f"openclaw-{args.name}")  # type: ignore[attr-defined]
        self._add_env_to_engine(self.engine, args)
        self.engine.add_workdir(args)
        self.engine.add_volume(self.config_file_path, "/etc/openclaw/ramalama.json")
        self.engine.add_args(args.openclaw_image)
        if args.ARGS:
            message = " ".join(args.ARGS)
            agent_verbose_args = ["--verbose"] if args.debug else []
            self.engine.add_args(
                "openclaw",
                "agent",
                *agent_verbose_args,
                "--session-id",
                "ramalama",
                "--message",
                message,
            )
        elif self.engine.use_tty():
            self.engine.add_args("openclaw", "tui", "--session", "main")
        else:
            verbose_flag = " --verbose" if args.debug else ""
            self.engine.add_args(
                "bash",
                "-c",
                f'msg="$(cat)"; exec openclaw agent{verbose_flag} --session-id ramalama --message "$msg"',
            )

    def _write_config(self, args: OpenClawArgsType) -> str:
        config: dict[str, Any] = {
            "models": {
                "providers": {
                    "openai": {
                        "api": "openai-completions",
                        "apiKey": "ramalama",
                        "baseUrl": f"http://localhost:{args.port}/v1",
                        "models": [],
                    },
                },
            },
            "agents": {
                "defaults": {
                    "model": {
                        "primary": f"openai/{self.model_name}",
                    },
                },
            },
            "gateway": {
                "mode": "local",
                "bind": "loopback",
                "port": args.openclaw_port,
            },
        }
        if args.workdir:
            config["agents"]["defaults"]["workspace"] = "/work"
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(config, tmp)
        tmp.close()
        return tmp.name

    def start_gateway(self) -> None:
        """Start the gateway container in detached mode."""
        run_cmd(self.gateway_engine.exec_args, stdout=None, stdin=None)
        self._gateway_started = True

    def _gateway_ready(self) -> bool:
        """Check whether the OpenClaw gateway container is running and listening on the configured port."""
        try:
            running = inspect(self.engine.args, self._gateway_name, format="{{ .State.Running }}", ignore_stderr=True)
            if running.lower() != "true":
                return False

            gateway_logs = logs(self.engine.args, self._gateway_name, ignore_stderr=True)
            port = str(self.args.openclaw_port)
            return any(token in gateway_logs for token in (f"127.0.0.1:{port}", f"localhost:{port}", f":{port}"))
        except Exception:
            return False

    def _wait_for_gateway_ready(self, timeout: int = 30) -> None:
        gateway_args = SimpleNamespace(**vars(self.engine.args))
        gateway_args.name = self._gateway_name
        wait_for_healthy(gateway_args, lambda _args: self._gateway_ready(), timeout=timeout)

    def run(self) -> None:
        """Start gateway, wait for it to become ready, then run the OpenClaw client."""
        try:
            self.start_gateway()
            self._wait_for_gateway_ready()
            super().run()
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        """Remove temporary config file and stop gateway container."""
        try:
            os.unlink(self.config_file_path)
        except FileNotFoundError:
            pass
        if self._gateway_started:
            self.engine.args.ignore = True  # type: ignore[attr-defined]
            stop_container(self.engine.args, self._gateway_name, remove=True)

    def _add_state_dir_to_engine(self, engine: SandboxEngine, args: OpenClawArgsType) -> None:
        state_dir = getattr(args, "state_dir", None)
        if state_dir:
            engine.add_volume(state_dir, "/var/lib/openclaw", opts="rw")
            engine.add_env_option("OPENCLAW_STATE_DIR=/var/lib/openclaw")

    def _add_env_to_engine(self, engine: SandboxEngine, args: OpenClawArgsType) -> None:
        engine.add_env_option(f"OPENAI_BASE_URL=http://localhost:{args.port}/v1")
        engine.add_env_option("OPENAI_API_KEY=ramalama")
        engine.add_env_option("OPENCLAW_CONFIG_PATH=/etc/openclaw/ramalama.json")
        engine.add_env_option("OPENCLAW_SKIP_CHANNELS=1")
        engine.add_env_option("OPENCLAW_SKIP_GMAIL_WATCHER=1")
        engine.add_env_option("OPENCLAW_SKIP_CRON=1")
        engine.add_env_option("OPENCLAW_SKIP_CANVAS_HOST=1")
        if getattr(args, "debug", False):
            engine.add_env_option("OPENCLAW_LOG_LEVEL=debug")

    def dryrun(self) -> None:
        self.gateway_engine.dryrun()
        super().dryrun()


def run_sandbox_goose(args: GooseArgsType):
    run_sandbox(args, Goose)


def run_sandbox_opencode(args: OpenCodeArgsType):
    run_sandbox(args, OpenCode)


def run_sandbox_openclaw(args: OpenClawArgsType):
    run_sandbox(args, OpenClaw)


def run_sandbox(args: SandboxEngineArgsType, agent_cls: type[Agent]):
    """Orchestrate model server and sandbox containers."""

    if not args.container:  # type: ignore[attr-defined]
        raise ValueError("ramalama sandbox requires a container engine")

    args.port = compute_serving_port(args)  # type: ignore[attr-defined]

    model = New(args.MODEL, args)
    model.ensure_model_exists(args)

    runtime = get_runtime(ActiveConfig().runtime)
    cmd = runtime.handle_subcommand("serve", cast(argparse.Namespace, args))

    model.serve_nonblocking(args, cmd)  # type: ignore[union-attr]

    agent = agent_cls(args, model.model_alias)

    if args.dryrun:
        agent.dryrun()
        return

    try:
        # Wait for model server to be healthy
        model.wait_for_healthy(args)  # type: ignore[union-attr]

        # Launch agent
        agent.run()
    finally:
        args.ignore = True  # type: ignore[attr-defined]
        stop_container(args, args.name, remove=True)  # type: ignore[attr-defined]
