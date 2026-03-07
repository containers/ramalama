import platform

from ramalama.arg_types import BaseEngineArgsType
from ramalama.common import run_cmd
from ramalama.config import ActiveConfig
from ramalama.engine import Engine, stop_container
from ramalama.plugins.loader import get_runtime
from ramalama.transports.base import compute_serving_port
from ramalama.transports.transport_factory import New


class SandboxEngineArgsType(BaseEngineArgsType):
    ARGS: list[str]


class GooseEngineArgsType(SandboxEngineArgsType):
    goose_image: str
    workdir: str | None


class SandboxEngine(Engine):
    """Engine for running sandbox containers."""

    def __init__(self, args: SandboxEngineArgsType, *, model_name: str) -> None:
        self.model_name = model_name
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


class GooseEngine(SandboxEngine):
    """Goose-specific sandbox engine.

    Extends SandboxEngine with environment variables required by Goose, and
    workdir handling. If args are provided, they will be passed to Goose to
    process non-interactively. If there are no arguments and stdin is a tty,
    an interactive session will be started. Otherwise, instructions will be
    read from stdin.
    """

    def __init__(self, args: GooseEngineArgsType, *, model_name: str) -> None:
        super().__init__(args, model_name=model_name)
        self.add_name(f"goose-{self.args.name}")  # type: ignore[attr-defined]
        self.add_workdir()
        self.add_args(args.goose_image)
        if args.ARGS:
            self.add_args("run", "-t", " ".join(args.ARGS))
        elif self.use_tty():
            self.add_args("session")
        else:
            self.add_args("run", "-i", "-")

    def add_env_options(self) -> None:
        super().add_env_options()
        self.add_env_option("GOOSE_PROVIDER=openai")
        self.add_env_option(f"OPENAI_HOST=http://localhost:{self.args.port}")
        self.add_env_option("OPENAI_API_KEY=ramalama")
        self.add_env_option(f"GOOSE_MODEL={self.model_name}")
        self.add_env_option("GOOSE_TELEMETRY_ENABLED=false")
        self.add_env_option("GOOSE_CLI_SHOW_THINKING=true")

    def add_privileged_options(self) -> None:
        super().add_privileged_options()
        # The goose image needs to run as uid 1000 so it can write state to the
        # home directory in the image. Map uid 1000 to the local user (which is
        # mapped to intermediate uid/gid 0) so files can be written to /work if
        # required.
        if self.use_podman:
            if platform.system() != "Windows":
                self.add_args("--uidmap=+1000:0")

    def add_workdir(self):
        if self.args.workdir:
            self.add_volume(self.args.workdir, "/work", opts="rw")
            self.add_args("--workdir=/work")

    def run(self) -> None:
        run_cmd(self.exec_args, stdout=None, stdin=None)


def run_sandbox(args):
    """Orchestrate model server and sandbox containers."""

    args.port = compute_serving_port(args)

    model = New(args.MODEL, args)
    model.ensure_model_exists(args)

    runtime = get_runtime(ActiveConfig().runtime)
    cmd = runtime.handle_subcommand("serve", args)

    model.serve_nonblocking(args, cmd)

    goose = GooseEngine(
        args,
        model_name=model.model_alias,
    )

    if args.dryrun:
        goose.dryrun()
        return

    try:
        # Wait for model server to be healthy
        model.wait_for_healthy(args)

        # Launch Goose
        goose.run()
    finally:
        args.ignore = True
        stop_container(args, args.name, remove=True)
