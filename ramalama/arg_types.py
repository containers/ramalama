from dataclasses import make_dataclass
from typing import List, Protocol, get_type_hints

from ramalama.config import COLOR_OPTIONS, SUPPORTED_ENGINES, SUPPORTED_RUNTIMES, PathStr


def protocol_to_dataclass(proto_cls):
    hints = get_type_hints(proto_cls)
    fields = [(name, typ) for name, typ in hints.items()]
    return make_dataclass(f"{proto_cls.__name__}DC", fields)


class EngineArgType(Protocol):
    engine: SUPPORTED_ENGINES | None


EngineArgs = protocol_to_dataclass(EngineArgType)


class ContainerArgType(Protocol):
    container: bool | None


ContainerArgs = protocol_to_dataclass(ContainerArgType)


class StoreArgType(Protocol):
    engine: SUPPORTED_ENGINES | None
    container: bool
    store: str


StoreArgs = protocol_to_dataclass(StoreArgType)


class DefaultArgsType(Protocol):
    container: bool
    runtime: SUPPORTED_RUNTIMES
    store: PathStr
    debug: bool
    quiet: bool
    dryrun: bool
    engine: SUPPORTED_ENGINES
    noout: bool | None


DefaultArgs = protocol_to_dataclass(DefaultArgsType)


class ChatSubArgsType(Protocol):
    prefix: str
    url: str
    color: COLOR_OPTIONS
    list: bool
    model: str | None
    rag: str | None
    api_key: str | None
    ARGS: List[str] | None


ChatSubArgs = protocol_to_dataclass(ChatSubArgsType)


class ChatArgsType(DefaultArgsType, ChatSubArgsType):
    pass
