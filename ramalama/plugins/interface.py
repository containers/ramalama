import argparse
from abc import ABC, abstractmethod
from http.client import HTTPConnection
from typing import Any


class RuntimePlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    def build_command(self, command: str, args: argparse.Namespace) -> list[str]:
        """Dispatch to the appropriate _cmd_<command> method.

        Command strings map to method names by replacing ' --' with '_' and '-' with '_',
        then prefixing with '_cmd_'.  Examples:
          'run'       → _cmd_run
          'serve'     → _cmd_serve
          'run --rag' → _cmd_run_rag
        """
        method_name = "_cmd_" + command.replace(" --", "_").replace("-", "_")
        method = getattr(self, method_name, None)
        if method is None:
            raise NotImplementedError(f"{self.name} plugin does not implement command '{command}'")
        return method(args)

    def get_container_image(self, config: Any, gpu_type: str) -> str | None:
        return None

    def setup_args(self, args: argparse.Namespace) -> None:
        pass

    def validate_args(self, args: Any) -> None:
        """Validate runtime-specific argument constraints. Raise ValueError if invalid."""
        pass

    def register_subcommands(self, subparsers: "argparse._SubParsersAction") -> None:
        """Register runtime-specific subcommand parsers.

        Override to add subcommands that only apply to this runtime.
        Called from configure_subcommands() after universal commands are registered.
        """
        pass

    @property
    def health_check_timeout(self) -> int:
        """Seconds to wait for the runtime server to become healthy."""
        return 180

    def is_healthy(self, conn: HTTPConnection, args: Any, model_name: str | None = None) -> bool:
        """Check server health. Override to implement runtime-specific health checks."""
        raise NotImplementedError(f"Runtime plugin '{self.name}' does not implement is_healthy()")


class InferenceRuntimePlugin(RuntimePlugin, ABC):
    """Abstract base class for runtime plugins that support 'run' and 'serve' subcommands.

    Concrete subclasses must implement _cmd_run.  The hooks below have safe
    no-op defaults and can be overridden to customise per-runtime behaviour.
    """

    @abstractmethod
    def _cmd_run(self, args: argparse.Namespace) -> list[str]:
        """Build the command list for the 'run' subcommand."""

    def chat_prefix(self) -> str | None:
        """Return the chat prompt prefix for this runtime, or None to use the default."""
        return None

    def handle_nocontainer_chat(self, args: Any, transport: Any) -> "int | None":
        """Handle the non-container chat path.

        Return an exit code if the plugin handled chat, or None to fall through
        to the default chat.chat() call.  transport exposes _is_server_ready(port)
        and _cleanup_server_process(process).
        """
        return None

    def api_model_name(self, args: Any) -> "str | None":
        """Return the model name to include in API requests, or None to omit it."""
        return getattr(args, "model", None)
