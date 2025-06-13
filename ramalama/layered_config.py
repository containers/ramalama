from dataclasses import MISSING, fields
from functools import reduce
from typing import Any


def extract_defaults(cls) -> dict[str, Any]:
    result = {}
    for f in fields(cls):
        if f.default is not MISSING:
            result[f.name] = f.default
        elif f.default_factory is not MISSING:  # type: ignore
            result[f.name] = f.default_factory()  # type: ignore
    return result


class LayeredMixin:
    """Mixin class to handle layered configurations from multiple sources."""

    def __init__(self, *layers: dict[str, Any]):
        self._fields = {f.name for f in fields(self.__class__)}
        self._layers = [{k: layer[k] for k in layer.keys() & self._fields} for layer in layers]

        defaults = extract_defaults(self.__class__)
        merged = reduce(dict.__or__, reversed(self._layers), defaults)

        super().__init__(**merged)

    def is_set(self, name: str) -> bool:
        return any(name in layer for layer in self._layers)
