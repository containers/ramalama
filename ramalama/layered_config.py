from dataclasses import MISSING, fields, is_dataclass
from functools import reduce
from typing import Any, Type, get_type_hints


def deep_merge(left: dict, right: dict) -> dict:
    """Recursively merge override dict into base dict."""
    for key, value in right.items():
        if isinstance(left_value := left.get(key, None), dict) and isinstance(value, dict):
            left[key] = deep_merge(left_value, value)
        else:
            left[key] = value
    return left


def extract_defaults(cls) -> dict[str, Any]:
    result = {}
    for f in fields(cls):
        if f.default is not MISSING:
            result[f.name] = f.default
        elif f.default_factory is not MISSING:  # type: ignore
            result[f.name] = f.default_factory()  # type: ignore
    return result


def build_subconfigs(values: dict, obj: Type) -> dict:
    """Facilitates nesting configs by instantiating the child typed object from a dict

    NOTE: This implementation does not automatically coerce more complicated config structures
    involving types like (ConfigObj | None), or list[ConfigObj], etc...
    """

    dtypes: dict[str, Type] = get_type_hints(obj)
    for k, v in values.items():
        if isinstance(v, dict) and (subconfig_type := dtypes.get(k)) and is_dataclass(subconfig_type):
            values[k] = subconfig_type(**build_subconfigs(v, dtypes[k]))

    return values


class LayeredMixin:
    """Mixin class to handle layered configurations from multiple sources."""

    def __init__(self, *layers: dict[str, Any]):
        self._fields = {f.name for f in fields(self.__class__)}  # type: ignore[arg-type]
        self._layers = [{k: layer[k] for k in layer.keys() & self._fields} for layer in layers]

        defaults = extract_defaults(self.__class__)
        merged = defaults | reduce(deep_merge, reversed(self._layers))
        super().__init__(**build_subconfigs(merged, type(self)))

    def is_set(self, name: str) -> bool:
        return any(name in layer for layer in self._layers)
