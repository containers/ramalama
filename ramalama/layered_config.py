from collections import ChainMap
from dataclasses import MISSING, fields, is_dataclass
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
    def __init_subclass__(cls):
        bases = [b for b in cls.__mro__[1:] if is_dataclass(b)]
        if not bases:
            return
        if len(bases) > 1:
            raise TypeError("…only one dataclass base allowed…")
        cls._base = bases[0]
        cls._defaults = extract_defaults(cls._base)
        cls._fields = {f.name for f in fields(cls._base)}

    def __init__(self, *layers: dict[str, Any]):
        # only tracks fields defined in the base class
        layers = [{k: layer[k] for k in layer.keys() & self._fields} for layer in layers]

        # earliest layer wins
        merged = ChainMap(*layers, self._defaults)

        self._base.__init__(self, **merged)
        self._layers: list[dict[str, Any]] = layers

    def is_set(self, name: str) -> bool:
        return any(name in layer for layer in self._layers)
