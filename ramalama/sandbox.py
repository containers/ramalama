from __future__ import annotations

import argparse
import copy
import json
import platform
from collections.abc import Callable
from functools import partial
from http.client import HTTPConnection
from typing import Optional, cast

from ramalama.arg_types import BaseEngineArgsType
from ramalama.common import genname, run_cmd
from ramalama.config import ActiveConfig
from ramalama.engine import Engine, is_healthy, stop_container, wait_for_healthy
from ramalama.plugins.loader import get_runtime
from ramalama.transports.base import compute_serving_port
from ramalama.transports.transport_factory import New


def default_pi_image() -> str:
    return ActiveConfig().default_pi_image


def _pi_provider_id() -> str:
    return "llama-server"


def _add_common_sandbox_args(parser: argparse.ArgumentParser) -> None:
    """Add --workdir and --prompt arguments shared by all sandbox subcommands."""
    parser.add_argument(
        "-w",
        "--workdir",
        help="local directory to mount into the sandbox container at /work",
    )
    parser.add_argument(
        "--url",
        help="OpenAI compatible endpoint. Defaults to localhost with computed or given port.",
    )
    parser.add_argument(
        "--api-key",
        default="ramalama",
        help="OpenAI-compatible API key.",
    )
    parser.add_argument(
        "--prompt",
        dest="ARGS",
        help="instructions for the sandbox to process non-interactively",
    )


def _add_router_args(parser: argparse.ArgumentParser) -> None:
    """Add --models-max argument for router mode."""
    parser.add_argument(
        "--models-max",
        dest="models_max",
        type=int,
        default=1,
        help="maximum number of models to load concurrently in router mode",
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
    parser.add_argument("MODEL", nargs="*", default=[], completer=model_comp)
    parser.add_argument(
        "--goose-image",
        default="ghcr.io/aaif-goose/goose:1.43.0",
        completer=img_comp,
        help="Goose container image",
    )
    _add_common_sandbox_args(parser)
    _add_router_args(parser)
    parser.set_defaults(func=run_sandbox_goose)
    yield parser

    parser = subparsers.add_parser("opencode", help="run OpenCode in a sandbox, backed by a local AI Model")
    if getattr(runtime, "_add_inference_args", None):
        runtime._add_inference_args(parser, "serve")  # type: ignore[attr-defined]
    parser.add_argument("MODEL", nargs="*", default=[], completer=model_comp)
    parser.add_argument(
        "--opencode-image",
        default="ghcr.io/anomalyco/opencode:1.17.20",
        completer=img_comp,
        help="OpenCode container image",
    )
    _add_common_sandbox_args(parser)
    _add_router_args(parser)
    parser.set_defaults(func=run_sandbox_opencode)
    yield parser

    parser = subparsers.add_parser("pi", help="run Pi in a sandbox, backed by a local AI Model")
    if getattr(runtime, "_add_inference_args", None):
        runtime._add_inference_args(parser, "serve")  # type: ignore[attr-defined]
    parser.add_argument("MODEL", nargs="*", default=[], completer=model_comp)
    parser.add_argument(
        "--pi-image",
        default=default_pi_image(),
        completer=img_comp,
        help="Pi container image",
    )
    _add_common_sandbox_args(parser)
    _add_router_args(parser)
    parser.set_defaults(func=run_sandbox_pi)
    yield parser


class SandboxEngineArgsType(BaseEngineArgsType):
    ARGS: Optional[str]
    workdir: Optional[str]
    url: Optional[str]
    api_key: Optional[str]
    start_model_server: bool
    name: str
    model: str


class SandboxEngine(Engine):
    """Engine for running sandbox containers."""

    def __init__(self, args: SandboxEngineArgsType) -> None:
        super().__init__(args)

    def base_args(self) -> None:
        self.add_args("run", "--rm", "-i")

    def is_tty_cmd(self) -> bool:
        return getattr(self.args, "subcommand", "") == "sandbox"

    def add_network(self) -> None:
        if getattr(self.args, "start_model_server", True):
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
            self.engine.add_args("run", "-t", args.ARGS)
        elif self.engine.use_tty():
            self.engine.add_args("session")
        else:
            self.engine.add_args("run", "-i", "-")

    def add_env_options(self, args: GooseArgsType) -> None:
        self.engine.add_env_option("GOOSE_PROVIDER=openai")
        self.engine.add_env_option(f"OPENAI_HOST={args.url}")
        self.engine.add_env_option(f"OPENAI_API_KEY={args.api_key}")
        if self.model_name:
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
            if args.ARGS:
                self.engine.add_args(args.ARGS)
        # Running on a tty with no arguments will start the TUI for an interactive session

    def add_env_options(self, args: OpenCodeArgsType) -> None:
        provider_config: dict = {
            "npm": "@ai-sdk/openai-compatible",
            "name": "RamaLama",
            "options": {
                "baseURL": f"{args.url}/v1",
                "apiKey": args.api_key,
            },
        }
        router_model_ids = getattr(args, "router_model_ids", None)
        if router_model_ids:
            provider_config["models"] = {mid: {"name": mid} for mid in router_model_ids}
        elif self.model_name:
            provider_config["models"] = {
                self.model_name: {
                    "name": self.model_name,
                },
            }
        config: dict = {
            "$schema": "https://opencode.ai/config.json",
            "provider": {
                "ramalama": provider_config,
            },
        }
        if self.model_name:
            config["model"] = f"ramalama/{self.model_name}"
        self.engine.add_env_option(f"OPENCODE_CONFIG_CONTENT={json.dumps(config)}")


class PiArgsType(SandboxEngineArgsType):
    pi_image: str


class Pi(Agent):
    """
    Run Pi in a sandbox.
    Environment variables and provider selection required by Pi will be set, and any workdir specified will be mounted
    into the container. If args are provided, they will be passed to Pi to process non-interactively. Otherwise, Pi
    will choose its interactive or print behavior based on whether stdin is attached to a tty.
    """

    def __init__(self, args: PiArgsType, model_name: str) -> None:
        super().__init__(args, model_name)
        provider_id = _pi_provider_id()
        self.engine.add_name(f"pi-{args.name}")  # type: ignore[attr-defined]
        self.add_provider_discovery_env(args)
        self.engine.add_workdir(args)
        self.engine.add_args(args.pi_image)
        pi_args = ["--provider", provider_id]
        if self.model_name:
            pi_args += ["--model", self.model_name]
        if args.ARGS:
            pi_args += ["-p", args.ARGS]
        self.engine.add(pi_args)

    def add_provider_discovery_env(self, args: PiArgsType) -> None:
        # pi-llama-server discovers and registers providers from LLAMA_SERVER_URL;
        # --provider then selects the matching provider id for the active session.
        self.engine.add_env_option(f"LLAMA_SERVER_URL={args.url}")


def run_sandbox_goose(args: GooseArgsType):
    run_sandbox(args, Goose)


def run_sandbox_opencode(args: OpenCodeArgsType):
    run_sandbox(args, OpenCode)


def run_sandbox_pi(args: PiArgsType):
    run_sandbox(args, Pi)


def run_sandbox(args: SandboxEngineArgsType, agent_cls: type[Agent]) -> None:
    """Orchestrate model server and sandbox containers."""

    if not args.container:  # type: ignore[attr-defined]
        raise ValueError("ramalama sandbox requires a container engine")

    sb_args = copy.copy(args)
    sb_args.start_model_server = args.url is None
    models: list[str] = list(args.MODEL)  # type: ignore[arg-type]

    if not sb_args.start_model_server:
        sb_args.name = sb_args.name or genname()
        model_name = models[0] if len(models) == 1 else ""
        if sb_args.dryrun:
            agent = agent_cls(sb_args, model_name)
            agent.engine.dryrun()
            return

        # Just launch agent
        agent = agent_cls(sb_args, model_name)
        agent.run()
        return

    sb_args.port = compute_serving_port(sb_args)
    sb_args.url = f"http://localhost:{sb_args.port}"
    if len(models) == 1:
        sb_args.MODEL = models[0]
        _run_sandbox_single_model(sb_args, agent_cls)
    else:
        _run_sandbox_router(sb_args, agent_cls)


def _run_sandbox_single_model(args: SandboxEngineArgsType, agent_cls: type[Agent]) -> None:
    """Run sandbox with a single model (original behavior)."""
    model = New(args.MODEL, args)

    if args.dryrun:
        agent = agent_cls(args, model.model_alias)
        agent.engine.dryrun()
        return

    model.ensure_model_exists(args)

    runtime = get_runtime(ActiveConfig().runtime)
    cmd = runtime.handle_subcommand("serve", cast(argparse.Namespace, args))

    model.serve_nonblocking(args, cmd)  # type: ignore[union-attr]
    agent = agent_cls(args, model.model_alias)

    try:
        model.wait_for_healthy(args)  # type: ignore[union-attr]
        agent.run()
    finally:
        args.ignore = True  # type: ignore[attr-defined]
        stop_container(args, args.name, remove=True)  # type: ignore[attr-defined]


def _query_router_models(port: int | str) -> list[str]:
    """Query the llama.cpp router server for available model IDs."""
    conn = None
    try:
        conn = HTTPConnection("127.0.0.1", int(port), timeout=5)
        conn.request("GET", "/v1/models")
        resp = conn.getresponse()
        if resp.status != 200:
            return []
        body = json.loads(resp.read())
        return [m.get("id", "") for m in body.get("data", []) if m.get("id")]
    except Exception:
        return []
    finally:
        if conn:
            conn.close()


def _run_sandbox_router(args: SandboxEngineArgsType, agent_cls: type[Agent]) -> None:
    """Run sandbox in router mode (zero or multiple models)."""
    runtime = get_runtime(ActiveConfig().runtime)

    serve_router = getattr(runtime, "serve_router_nonblocking", None)
    if serve_router is None:
        raise ValueError("Router mode (zero or multiple models) is only supported with the llama.cpp runtime.")

    serve_router(cast(argparse.Namespace, args))

    if args.dryrun:
        agent = agent_cls(args, "")
        agent.engine.dryrun()
        return

    try:
        wait_for_healthy(args, partial(is_healthy))

        if args.port is None:
            raise ValueError("Router mode requires a resolved serving port")
        model_ids = _query_router_models(args.port)
        args.router_model_ids = model_ids  # type: ignore[attr-defined]
        first_model = model_ids[0] if model_ids else ""

        agent = agent_cls(args, first_model)
        agent.run()
    finally:
        args.ignore = True  # type: ignore[attr-defined]
        stop_container(args, args.name, remove=True)  # type: ignore[attr-defined]
