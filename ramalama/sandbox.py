import argparse
import platform
from collections.abc import Callable

from ramalama.arg_types import BaseEngineArgsType
from ramalama.common import run_cmd
from ramalama.config import ActiveConfig
from ramalama.engine import Engine, stop_container
from ramalama.plugins.loader import get_runtime
from ramalama.transports.base import compute_serving_port
from ramalama.transports.transport_factory import New


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
    yield parser


class SandboxEngineArgsType(BaseEngineArgsType):
    ARGS: list[str]


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
    workdir: str | None


class Goose:
    """
    Run Goose in a sandbox.
    Environment variables required by Goose will be set, and any workdir specified will be mounted into the container.
    If args are provided, they will be passed to Goose to process non-interactively. If there are no arguments and stdin
    is a tty, an interactive session will be started. Otherwise, instructions will be read from stdin.
    """

    def __init__(self, args: GooseArgsType, model_name: str) -> None:
        self.engine = SandboxEngine(args)
        if self.engine.use_podman:
            if platform.system() != "Windows":
                self.engine.add_args("--uidmap=+1000:0")
        self.engine.add_name(f"goose-{args.name}")  # type: ignore[attr-defined]
        self.add_env_options(args, model_name)
        self.add_workdir(args)
        self.engine.add_args(args.goose_image)
        if args.ARGS:
            self.engine.add_args("run", "-t", " ".join(args.ARGS))
        elif self.engine.use_tty():
            self.engine.add_args("session")
        else:
            self.engine.add_args("run", "-i", "-")

    def add_env_options(self, args: GooseArgsType, model_name: str) -> None:
        self.engine.add_env_option("GOOSE_PROVIDER=openai")
        self.engine.add_env_option(f"OPENAI_HOST=http://localhost:{args.port}")
        self.engine.add_env_option("OPENAI_API_KEY=ramalama")
        self.engine.add_env_option(f"GOOSE_MODEL={model_name}")
        self.engine.add_env_option("GOOSE_TELEMETRY_ENABLED=false")
        self.engine.add_env_option("GOOSE_CLI_SHOW_THINKING=true")

    def add_workdir(self, args: GooseArgsType):
        if args.workdir:
            self.engine.add_volume(args.workdir, "/work", opts="rw")
            self.engine.add_args("--workdir=/work")

    def run(self) -> None:
        run_cmd(self.engine.exec_args, stdout=None, stdin=None)


def run_sandbox(args):
    """Orchestrate model server and sandbox containers."""

    args.port = compute_serving_port(args)

    model = New(args.MODEL, args)
    model.ensure_model_exists(args)

    runtime = get_runtime(ActiveConfig().runtime)
    cmd = runtime.handle_subcommand("serve", args)

    model.serve_nonblocking(args, cmd)

    goose = Goose(args, model.model_alias)

    if args.dryrun:
        goose.engine.dryrun()
        return

    try:
        # Wait for model server to be healthy
        model.wait_for_healthy(args)

        # Launch Goose
        goose.run()
    finally:
        args.ignore = True
        stop_container(args, args.name, remove=True)
