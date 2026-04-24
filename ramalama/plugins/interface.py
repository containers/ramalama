from __future__ import annotations

import argparse
from abc import ABC, abstractmethod
from http.client import HTTPConnection
from typing import Any, Optional


class RuntimePlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    def get_container_image(self, config: Any, gpu_type: str) -> Optional[str]:
        return None

    def register_subcommands(self, subparsers: "argparse._SubParsersAction") -> None:
        """Register runtime-specific subcommand parsers.

        Override to add subcommands that only apply to this runtime.
        Called from configure_subcommands() after universal commands are registered.
        """
        pass

    def post_process_args(self, args: argparse.Namespace) -> None:
        """Mutate and validate args after parsing. Override in concrete plugins."""
        pass

    def handle_subcommand(self, command: str, args: argparse.Namespace) -> list[str]:
        """Handle the given subcommand. Override in concrete plugins."""
        raise NotImplementedError(f"{self.name} plugin does not implement handle_subcommand()")

    @property
    def service_ready_check_timeout(self) -> int:
        """Seconds to wait for the runtime server to become ready."""
        return 180

    def service_ready_check(self, conn: HTTPConnection, args: Any, model_name: Optional[str] = None) -> bool:
        """Check if the service is ready to receive requests."""
        return True


class InferenceRuntimePlugin(RuntimePlugin, ABC):
    """Abstract base class for inference runtime plugins."""

    @property
    def chat_include_model_name(self) -> bool:
        """Whether to include the model name in chat API requests."""
        return True
