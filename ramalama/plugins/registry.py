from importlib.metadata import entry_points
from typing import Generic, Type, TypeVar

T = TypeVar("T")


class PluginRegistry(Generic[T]):
    """Generic registry for any ramalama plugin type, keyed by entry point group."""

    def __init__(self, group: str, base_class: Type[T]):
        self.group = group
        self.base_class = base_class
        self._plugins: dict[str, T] | None = None

    def load(self) -> dict[str, T]:
        if self._plugins is None:
            self._plugins = {}
            for ep in entry_points(group=self.group):
                plugin: T = ep.load()()
                self._plugins[plugin.name] = plugin  # type: ignore[attr-defined]
        return self._plugins

    def get(self, name: str) -> T | None:
        return self.load().get(name)
