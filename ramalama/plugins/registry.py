from __future__ import annotations

import sys
from importlib.metadata import entry_points
from typing import Generic, Optional, Type, TypeVar

T = TypeVar("T")


class PluginRegistry(Generic[T]):
    """Generic registry for any ramalama plugin type, keyed by entry point group."""

    def __init__(self, group: str, base_class: Type[T]):
        self.group = group
        self.base_class = base_class
        self._plugins: Optional[dict[str, T]] = None

    def load(self) -> dict[str, T]:
        if self._plugins is None:
            self._plugins = {}
            if sys.version_info >= (3, 10):
                eps = entry_points(group=self.group)
            else:
                eps = entry_points().get(self.group, [])  # type: ignore[call-overload]
            for ep in eps:
                plugin: T = ep.load()()
                self._plugins[plugin.name] = plugin  # type: ignore[attr-defined]
        return self._plugins

    def get(self, name: str) -> Optional[T]:
        return self.load().get(name)
