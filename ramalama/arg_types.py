from __future__ import annotations

import argparse
from dataclasses import make_dataclass
from typing import List, Optional, Protocol, Union, get_type_hints

from ramalama.config_types import COLOR_OPTIONS, SUPPORTED_ENGINES, SUPPORTED_RUNTIMES, PathStr


def protocol_to_dataclass(proto_cls):
    hints = get_type_hints(proto_cls)
    fields = [(name, typ) for name, typ in hints.items()]
    return make_dataclass(f"{proto_cls.__name__}DC", fields)


class EngineArgType(Protocol):
    engine: Optional[SUPPORTED_ENGINES]


EngineArgs = protocol_to_dataclass(EngineArgType)


class ContainerArgType(Protocol):
    container: Optional[bool]


ContainerArgs = protocol_to_dataclass(ContainerArgType)


class StoreArgType(Protocol):
    engine: Optional[SUPPORTED_ENGINES]
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
    pull: Optional[str]
    network: Optional[str]
    oci_runtime: Optional[str]
    selinux: Optional[bool]
    nocapdrop: Optional[bool]
    device: Optional[List[str]]
    podman_keep_groups: Optional[bool]
    # Optional attributes for labels
    MODEL: Optional[str]
    runtime: Optional[str]
    port: Union[str, int, None]  # Can be string (e.g., "8080:8080") or int
    subcommand: Optional[str]


BaseEngineArgs = protocol_to_dataclass(BaseEngineArgsType)


class DefaultArgsType(Protocol):
    container: bool
    runtime: SUPPORTED_RUNTIMES
    store: PathStr
    debug: bool
    quiet: bool
    dryrun: bool
    engine: SUPPORTED_ENGINES
    noout: Optional[bool]


DefaultArgs = protocol_to_dataclass(DefaultArgsType)


class ChatSubArgsType(Protocol):
    prefix: str
    url: str
    color: COLOR_OPTIONS
    list: bool
    attachments: Optional[List[PathStr]]
    model: Optional[str]
    rag: Optional[str]
    api_key: Optional[str]
    ARGS: Optional[List[str]]
    max_tokens: Optional[int]
    temp: Optional[float]


ChatSubArgs = protocol_to_dataclass(ChatSubArgsType)


class ChatArgsType(DefaultArgsType, ChatSubArgsType):
    ignore: Optional[bool]  # runtime-only


class RagArgsType(DefaultArgsType, Protocol):
    """Args when using RAG functionality - wraps model args"""

    model_args: argparse.Namespace
    model_host: str
    model_port: int
    rag: str


RagArgs = protocol_to_dataclass(RagArgsType)
