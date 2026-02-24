import subprocess
from dataclasses import is_dataclass, make_dataclass
from typing import Any, Literal, Protocol, TypeVar, Union, cast, get_args, get_origin, get_type_hints

from ramalama.config_types import COLOR_OPTIONS, SUPPORTED_ENGINES, SUPPORTED_RUNTIMES, PathStr

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


class SchemaFactory(Protocol[T_co]):
    def __call__(self, *args: Any, **kwargs: Any) -> T_co: ...


def _matches_type(value: Any, anno: Any) -> bool:
    if anno is Any:
        return True

    origin = get_origin(anno)
    args = get_args(anno)

    if origin is Union:
        return any(_matches_type(value, a) for a in args)

    if origin is Literal:
        return value in args

    if origin is list:
        if not isinstance(value, list):
            return False
        (inner,) = args or (Any,)
        return all(_matches_type(v, inner) for v in value)

    if origin is dict:
        if not isinstance(value, dict):
            return False
        k_t, v_t = args or (Any, Any)
        return all(_matches_type(k, k_t) and _matches_type(v, v_t) for k, v in value.items())

    if isinstance(anno, type):
        return isinstance(value, anno)

    # fallback for unsupported typing forms
    return True


def narrow_by_schema(args: object, schema: SchemaFactory[T]) -> T:
    hints = get_type_hints(schema)
    values: dict[str, Any] = {}

    for field, anno in hints.items():
        if not hasattr(args, field):
            raise ValueError(f"missing argument: {field}")
        value = getattr(args, field)
        if not _matches_type(value, anno):
            raise ValueError(f"invalid type for {field}: expected {anno}, got {type(value)}")
        values[field] = value

    if is_dataclass(schema):
        return schema(**values)  # type: ignore[misc]

    return cast(T, args)


def protocol_to_dataclass(proto_cls):
    hints = get_type_hints(proto_cls)
    fields = [(name, typ) for name, typ in hints.items()]
    return make_dataclass(f"{proto_cls.__name__}DC", fields)


def narrow_args(args: object) -> Any:
    return cast(Any, args)


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
    engine: SUPPORTED_ENGINES | None
    noout: bool | None


DefaultArgs = protocol_to_dataclass(DefaultArgsType)


class ChatSubArgsType(Protocol):
    ARGS: list[str] | None
    prefix: str
    url: str
    color: COLOR_OPTIONS
    list: bool
    model: str | None
    rag: str | None
    api_key: str | None
    max_tokens: int | None
    temp: float | None


ChatSubArgs = protocol_to_dataclass(ChatSubArgsType)


class ChatArgsType(DefaultArgsType, ChatSubArgsType, Protocol):
    # Runtime-only fields injected by the transport flow.
    ignore: bool | None  # runtime-only
    initial_connection: bool | None
    keepalive: str | None
    name: str | None
    server_process: subprocess.Popen[Any] | None
    mcp: list[str] | None
    summarize_after: int


class GenerateArgType(Protocol):
    gen_type: str
    output_dir: str


class PostParseCoreArgsType(DefaultArgsType, Protocol):
    subcommand: str | None


class PostParseModelInputRawArgsType(Protocol):
    MODEL: str | list[str]


class PostParseModelInputNormalizedArgsType(PostParseModelInputRawArgsType, Protocol):
    INITIAL_MODEL: str | list[str]
    UNRESOLVED_MODEL: str | list[str]
    model: str | list[str]


class PostParseAddToUnitArgsType(Protocol):
    add_to_unit: list[str] | None
    generate: GenerateArgType | str | None


class PostParseRuntimeArgsRawType(Protocol):
    runtime_args: str


class PostParseRuntimeArgsNormalizedType(Protocol):
    runtime_args: list[str]


class PostParsePullArgsType(Protocol):
    pull: str | None
    engine: SUPPORTED_ENGINES | None


class ServeRunArgsType(DefaultArgsType, Protocol):
    """Args for serve and run commands"""

    MODEL: str
    port: str | int | None
    name: str | None
    rag: str | None
    subcommand: str
    detach: bool | None
    api: str | None
    image: str
    host: str | None
    generate: GenerateArgType | str | None
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
    rag_image: str
    ignore: bool | None  # runtime-only


ServeRunArgs = protocol_to_dataclass(ServeRunArgsType)


class ModelArgsType(DefaultArgsType, Protocol):
    MODEL: str


class SourceTargetArgsType(DefaultArgsType, Protocol):
    SOURCE: str
    TARGET: str | None
    dryrun: bool
    carimage: str
    type: Literal["artifact", "car", "raw"]


class ConvertArgsType(DefaultArgsType, Protocol):
    SOURCE: str
    TARGET: str | None
    container: bool
    carimage: str
    type: Literal["artifact", "car", "raw"]
    rag_image: str
    image: str
    gguf: str | None
    subcommand: str | None


class RmArgsType(DefaultArgsType, Protocol):
    all: bool
    ignore: bool
    MODEL: list[str]


class InspectArgsType(DefaultArgsType, Protocol):
    MODEL: str
    all: bool
    get: str
    json: bool
    pull: str | None


class RegistryArgsType(DefaultArgsType, Protocol):
    REGISTRY: str | None


class LoginArgsType(RegistryArgsType, Protocol):
    tlsverify: bool | str
    authfile: str | None
    username: str | None
    password: str | None
    passwordstdin: bool


class ListArgsType(DefaultArgsType, Protocol):
    all: bool
    json: bool
    noheading: bool
    sort: Literal["name", "modified", "size"]
    order: str


class StopArgsType(DefaultArgsType, Protocol):
    all: bool
    NAME: str | None
    ignore: bool
    format: str


class DaemonStartArgsType(DefaultArgsType, Protocol):
    pull: str
    host: str
    port: str | int
    image: str


class DaemonRunArgsType(DefaultArgsType, Protocol):
    host: str
    port: str | int


class RagArgsType(ServeRunArgsType, Protocol):
    """Args when using RAG functionality - wraps model args"""

    model_args: ServeRunArgsType
    model_host: str
    model_port: str | int
    rag: str  # type: ignore


RagArgs = protocol_to_dataclass(RagArgsType)
