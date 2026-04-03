import argparse
import json
import platform
from collections.abc import Callable
from typing import cast

from ramalama.arg_types import BaseEngineArgsType
from ramalama.common import run_cmd
from ramalama.config import ActiveConfig
from ramalama.engine import Engine, stop_container
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


class SandboxEngineArgsType(BaseEngineArgsType):
    ARGS: list[str]
    workdir: str | None


class SandboxEngine(Engine):
    """Engine for running sandbox containers."""

    def __init__(self, args: SandboxEngineArgsType) -> None:
        super().__init__(args)

    def base_args(self) -> None:
        self.add_args("run", "--rm", "-i")

    def is_tty_cmd(self) -> bool:
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
        if args.ARGS:
            self.engine.add_args("run", " ".join(args.ARGS))
        elif not self.engine.use_tty():
            self.engine.add_args("run", "-")

    def add_env_options(self, args: OpenCodeArgsType) -> None:
        config = {
            "$schema": "https://opencode.ai/config.json",
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


def run_sandbox_goose(args: GooseArgsType):
    run_sandbox(args, Goose)


def run_sandbox_opencode(args: OpenCodeArgsType):
    run_sandbox(args, OpenCode)


def run_sandbox(args: SandboxEngineArgsType, agent_cls: type[Agent]):
    """Orchestrate model server and sandbox containers."""

    if not args.container:  # type: ignore[attr-defined]
        raise ValueError("ramalama sandbox requires a container engine")

    args.port = compute_serving_port(args)

    model = New(args.MODEL, args)
    model.ensure_model_exists(args)

    runtime = get_runtime(ActiveConfig().runtime)
    cmd = runtime.handle_subcommand("serve", cast(argparse.Namespace, args))

    model.serve_nonblocking(args, cmd)  # type: ignore[union-attr]

    agent = agent_cls(args, model.model_alias)

    if args.dryrun:
        agent.engine.dryrun()
        return

    try:
        # Wait for model server to be healthy
        model.wait_for_healthy(args)  # type: ignore[union-attr]

        # Launch agent
        agent.run()
    finally:
        args.ignore = True  # type: ignore[attr-defined]
        stop_container(args, args.name, remove=True)  # type: ignore[attr-defined]
