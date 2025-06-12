from abc import ABC
from dataclasses import MISSING, field, fields, is_dataclass, make_dataclass
from typing import Any, Generic, Type, TypeVar, get_type_hints

BaseType = TypeVar("BaseType")


class _UNSET:
    pass


class Layer(Generic[BaseType]):
    pass


def make_layer_class(base_cls) -> Type[Layer]:
    """
    Layers are dataclasses that hold configuration for a specific layer.
    Unlike the base class, each layer can be left empty or partially filled.
    """
    hints = get_type_hints(base_cls)
    base_fields: list[tuple[str, Any, Any]] = []
    for f in fields(base_cls):
        # make each field `OriginalType | _UNSET`
        typ = hints[f.name] | _UNSET
        base_fields.append((f.name, typ, field(default=_UNSET)))

    # mix in our generic Layer[base_cls] so static checkers see the relationship
    name = f"{base_cls.__name__}Layer"
    bases = (Layer[base_cls],)
    return make_dataclass(name, base_fields, bases=bases)


def extract_defaults(cls) -> dict[str, Any]:
    """
    Extracts default values from a dataclass, returning a dictionary
    """

    if not is_dataclass(cls):
        raise TypeError(f"{cls} is not a dataclass")

    result = {}
    for f in fields(cls):
        if f.default is not MISSING:
            result[f.name] = f.default
        elif f.default_factory is not MISSING:  # type: ignore
            result[f.name] = f.default_factory()  # type: ignore
    return result


class LayeredMixin(ABC, Generic[BaseType]):
    """A mixin for creating layered configurations based on a dataclass.
    This mixin allows you to define a base configuration dataclass and
    create multiple layers of configuration from different sources.
    This is similar to ChainMap but passes typing through to the finalized dataclass.

    The finalized class will have the same fields as the base dataclass, with
    values collected from the layers provided during initialization.
    """

    _base_config: Type[BaseType]
    _layer_cls: Type[Layer]
    _base_fields: tuple
    _defaults: dict[str, Any]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        dataclass_bases = [b for b in cls.__mro__[1:] if is_dataclass(b)]
        if not dataclass_bases:
            return
        if len(dataclass_bases) > 1:
            raise TypeError(
                f"Ambiguous dataclass bases {dataclass_bases!r}, "
                "please inherit only one dataclass or use a single combined base."
            )
        base = dataclass_bases[0]
        cls._base_config = base
        cls._layer_cls = make_layer_class(base)
        cls._base_fields = fields(base)
        cls._defaults = extract_defaults(base)

    def __init__(self, layers: list[dict[str, Any]]) -> None:
        values = self._defaults.copy()
        self._layers = tuple(self._layer_cls(**L) for L in layers)

        for f in self._base_fields:
            for layer in self._layers:
                v = getattr(layer, f.name)
                if v is not _UNSET:
                    values[f.name] = v
                    break
            else:
                if f.name not in values and f.init:
                    raise ValueError(f"Missing required field: {f.name!r}")

        # call your dataclass’s __init__
        self._base_config.__init__(self, **values)

    def as_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in self._base_fields}

    def is_set(self, name: str) -> bool:
        if name not in {f.name for f in self._base_fields}:
            return False
        return any(getattr(layer, name) is not _UNSET for layer in self._layers)

    @property
    def layers(self) -> tuple[Layer[BaseType], ...]:
        """
        A tuple of your generated Layer[BaseConfig] instances.
        """
        return self._layers
