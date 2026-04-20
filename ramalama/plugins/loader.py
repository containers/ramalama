from __future__ import annotations

import argparse

from ramalama.plugins.interface import RuntimePlugin
from ramalama.plugins.registry import PluginRegistry

# Registry for runtime plugins (entry point group: "ramalama.runtimes.v1alpha")
# Future plugin types register their own PluginRegistry with a distinct group name, e.g.:
#   CHAT_PLUGIN_REGISTRY = PluginRegistry("ramalama.chat_providers", ChatPlugin)
_RUNTIME_REGISTRY: PluginRegistry[RuntimePlugin] = PluginRegistry("ramalama.runtimes.v1alpha", RuntimePlugin)  # type: ignore[type-abstract]


def get_all_runtimes() -> dict[str, RuntimePlugin]:
    return _RUNTIME_REGISTRY.load()


def get_runtime(name: str) -> RuntimePlugin:
    plugin = _RUNTIME_REGISTRY.get(name)
    if plugin is None:
        raise ValueError(f"Unknown runtime: '{name}'")
    return plugin


def assemble_command(cli_args: argparse.Namespace) -> list[str]:
    runtime = str(cli_args.runtime)
    command = str(cli_args.subcommand)
    return get_runtime(runtime).handle_subcommand(command, cli_args)
