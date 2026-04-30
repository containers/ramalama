from __future__ import annotations

import argparse
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import asdict, fields
from http.client import HTTPConnection
from typing import Any, Optional, Type


class RuntimePlugin(ABC):
    config_type: Optional[Type] = None

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    def config_key(self) -> str:
        return self.name.replace(".", "_").replace("-", "_")

    def get_runtime_config(self, config: Any) -> Any:
        """Return the typed runtime config, hydrated from config.runtimes."""
        if self.config_type is None:
            return None
        raw = config.runtimes.get(self.config_key, {})
        if not isinstance(raw, Mapping):
            raise ValueError(f"config.runtimes.{self.config_key} must be a mapping, got {type(raw).__name__}")
        known = {f.name for f in fields(self.config_type)}
        return self.config_type(**{k: v for k, v in raw.items() if k in known})

    def sync_args_to_runtime_config(self, args: argparse.Namespace, config: Any) -> None:
        """Sync CLI args into the runtime config section."""
        if self.config_type is None:
            return
        rt_config = self.get_runtime_config(config)
        rt_fields = {f.name for f in fields(rt_config)}
        for arg_name in vars(args).keys() & rt_fields:
            if getattr(args, arg_name) != getattr(rt_config, arg_name):
                setattr(rt_config, arg_name, getattr(args, arg_name))
        config.runtimes[self.config_key] = asdict(rt_config)

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
