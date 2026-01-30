from dataclasses import make_dataclass
from subprocess import Popen
from typing import Any, List, Protocol, get_type_hints

from ramalama.config_types import COLOR_OPTIONS, SUPPORTED_ENGINES, SUPPORTED_RUNTIMES, PathStr


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


class BaseEngineArgsType(Protocol):
    """Arguments required by BaseEngine.__init__"""

    # Required attributes (accessed directly)
    engine: SUPPORTED_ENGINES
    dryrun: bool
    quiet: bool
    image: str
    # Optional attributes (accessed via getattr)
    pull: str | None
    network: str | None
    oci_runtime: str | None
    selinux: bool | None
    nocapdrop: bool | None
    device: list[str] | None
    podman_keep_groups: bool | None
    rag: str | None
    # Optional attributes for labels
    MODEL: str | None
    runtime: str | None
    port: str | int | None  # Can be string (e.g., "8080:8080") or int
    subcommand: str | None


BaseEngineArgs = protocol_to_dataclass(BaseEngineArgsType)


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
    max_tokens: int | None
    temp: float | None


ChatSubArgs = protocol_to_dataclass(ChatSubArgsType)


class ChatArgsType(DefaultArgsType, ChatSubArgsType):
    ignore: bool | None  # runtime-only
    server_process: Popen[Any] | None  # runtime-only
    name: str | None  # runtime-only


class ServeRunArgsType(DefaultArgsType, Protocol):
    """Args for serve and run commands"""

    MODEL: str
    port: int | None
    name: str | None
    rag: str | None
    subcommand: str
    detach: bool | None
    api: str | None
    image: str
    host: str | None
    generate: str | None
    context: int
    cache_reuse: int
    authfile: str | None
    device: list[str] | None
    env: list[str]
    ARGS: list[str] | None  # For run command
    mcp: list[str] | None
    summarize_after: int
    # Chat/run specific options
    color: COLOR_OPTIONS
    prefix: str
    rag_image: str | None
    ignore: bool | None  # runtime-only


ServeRunArgs = protocol_to_dataclass(ServeRunArgsType)


class RagArgsType(ServeRunArgsType, Protocol):
    """Args when using RAG functionality - wraps model args"""

    model_args: ServeRunArgsType
    model_host: str
    model_port: int
    rag: str  # type: ignore


RagArgs = protocol_to_dataclass(RagArgsType)
