import copy
import threading
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeAlias
from urllib.parse import urlparse

from ramalama.arg_types import StoreArgType
from ramalama.chat_providers.api_providers import get_chat_provider
from ramalama.common import rm_until_substring
from ramalama.config import DEFAULT_TRANSPORT, get_config
from ramalama.path_utils import file_uri_to_path
from ramalama.transports.api import APITransport
from ramalama.transports.base import MODEL_TYPES, Transport
from ramalama.transports.huggingface import Huggingface
from ramalama.transports.modelscope import ModelScope
from ramalama.transports.oci import OCI
from ramalama.transports.ollama import Ollama
from ramalama.transports.rlcr import RamalamaContainerRegistry
from ramalama.transports.url import URL

CLASS_MODEL_TYPES: TypeAlias = Huggingface | Ollama | OCI | URL | ModelScope | RamalamaContainerRegistry | APITransport


@dataclass(frozen=True)
class TransportRegistryEntry:
    model_cls: type[CLASS_MODEL_TYPES]
    prefixes: tuple[str, ...]
    creator: Callable[["TransportFactory"], Callable[[], CLASS_MODEL_TYPES]]
    transport_name: str | None = None


TRANSPORT_REGISTRY: tuple[TransportRegistryEntry, ...] = (
    TransportRegistryEntry(
        model_cls=Huggingface,
        prefixes=("huggingface://", "hf://", "hf.co/"),
        creator=lambda factory: factory.create_huggingface,
        transport_name="huggingface",
    ),
    TransportRegistryEntry(
        model_cls=ModelScope,
        prefixes=("modelscope://", "ms://"),
        creator=lambda factory: factory.create_modelscope,
        transport_name="modelscope",
    ),
    TransportRegistryEntry(
        model_cls=Ollama,
        prefixes=("ollama://", "ollama.com/library/"),
        creator=lambda factory: factory.create_ollama,
        transport_name="ollama",
    ),
    TransportRegistryEntry(
        model_cls=OCI,
        prefixes=("oci://", "docker://"),
        creator=lambda factory: factory.create_oci,
        transport_name="oci",
    ),
    TransportRegistryEntry(
        model_cls=RamalamaContainerRegistry,
        prefixes=("rlcr://",),
        creator=lambda factory: factory.create_rlcr,
        transport_name="rlcr",
    ),
    TransportRegistryEntry(
        model_cls=URL,
        prefixes=("http://", "https://", "file:"),
        creator=lambda factory: factory.create_url,
    ),
    TransportRegistryEntry(
        model_cls=APITransport,
        prefixes=("openai://",),
        creator=lambda factory: factory.create_api_transport,
    ),
)

_default_transport_warned = False
_default_transport_warned_lock = threading.Lock()


def _set_default_transport_warned(value: bool) -> None:
    """Test helper for resetting warning state with the same lock as production code."""
    global _default_transport_warned
    with _default_transport_warned_lock:
        _default_transport_warned = value


def _supported_named_transports() -> tuple[str, ...]:
    return tuple(sorted(entry.transport_name for entry in TRANSPORT_REGISTRY if entry.transport_name))


def _detect_prefixed_transport(model: str) -> TransportRegistryEntry | None:
    for entry in TRANSPORT_REGISTRY:
        if model.startswith(entry.prefixes):
            return entry
    return None


def _detect_named_transport(transport: str) -> TransportRegistryEntry | None:
    for entry in TRANSPORT_REGISTRY:
        if entry.transport_name == transport:
            return entry
    return None


class TransportFactory:
    def __init__(
        self,
        model: str,
        args: StoreArgType,
        transport: str = DEFAULT_TRANSPORT,
        ignore_stderr: bool = False,
    ):

        self.model = model
        self.store_path = args.store
        self.transport = transport
        self.engine = args.engine
        self.ignore_stderr = ignore_stderr
        self.container = args.container

        model_cls, _create = self.detect_model_model_type()

        self.model_cls = model_cls
        self._create = _create

        self.pruned_model = self.prune_model_input()
        self.draft_model: Transport | None = None

        model_draft = getattr(args, "model_draft", None)
        if model_draft:
            dm_args = copy.deepcopy(args)
            dm_args.model_draft = None  # type: ignore
            draft_model = TransportFactory(model_draft, dm_args, ignore_stderr=True).create()
            if not isinstance(draft_model, Transport):
                raise ValueError("Draft models must be local transports; hosted API transports are not supported.")
            self.draft_model = draft_model

    def detect_model_model_type(self) -> tuple[type[CLASS_MODEL_TYPES], Callable[[], CLASS_MODEL_TYPES]]:
        entry = _detect_prefixed_transport(self.model)
        if entry:
            return entry.model_cls, entry.creator(self)

        entry = _detect_named_transport(self.transport)
        if entry is None:
            supported = ", ".join(_supported_named_transports())
            raise KeyError(f'transport "{self.transport}" not supported. Must be one of: {supported}.')
        return entry.model_cls, entry.creator(self)

    def prune_model_input(self) -> str:

        if self.model_cls == URL and urlparse(self.model).scheme == "file":
            return file_uri_to_path(self.model)

        # remove protocol from model input
        pruned_model_input = rm_until_substring(self.model, "://")

        if self.model_cls == Huggingface:
            pruned_model_input = rm_until_substring(pruned_model_input, "hf.co/")
        elif self.model_cls == ModelScope:
            pruned_model_input = rm_until_substring(pruned_model_input, "modelscope.cn/")
        elif self.model_cls == Ollama:
            pruned_model_input = rm_until_substring(pruned_model_input, "ollama.com/library/")

        return pruned_model_input

    def validate_oci_model_input(self):
        if self.model.startswith("oci://") or self.model.startswith("docker://") or self.model.startswith("rlcr://"):
            return

        for t in MODEL_TYPES:
            if self.model.startswith(t + "://"):
                raise ValueError(f"{self.model} invalid: Only OCI Model types supported")

    def create(self) -> CLASS_MODEL_TYPES:
        return self._create()

    def create_huggingface(self) -> Huggingface:
        model = Huggingface(self.pruned_model, self.store_path)
        model.draft_model = self.draft_model
        return model

    def create_modelscope(self) -> ModelScope:
        model = ModelScope(self.pruned_model, self.store_path)
        model.draft_model = self.draft_model
        return model

    def create_ollama(self) -> Ollama:
        model = Ollama(self.pruned_model, self.store_path)
        model.draft_model = self.draft_model
        return model

    def create_rlcr(self) -> RamalamaContainerRegistry:
        if not self.container:
            raise ValueError("OCI containers cannot be used with the --nocontainer option.")

        if self.engine is None:
            raise ValueError("Constructing an OCI model factory requires an engine value")

        self.validate_oci_model_input()
        model = RamalamaContainerRegistry(
            model=self.pruned_model,
            model_store_path=self.store_path,
            conman=self.engine,
            ignore_stderr=self.ignore_stderr,
        )
        model.draft_model = self.draft_model
        return model

    def create_oci(self) -> OCI:
        if not self.container:
            raise ValueError("OCI containers cannot be used with the --nocontainer option.")

        if self.engine is None:
            raise ValueError("Constructing an OCI model factory requires an engine value")

        self.validate_oci_model_input()

        model = OCI(self.pruned_model, self.store_path, self.engine, self.ignore_stderr)
        model.draft_model = self.draft_model
        return model

    def create_url(self) -> URL:
        model = URL(self.pruned_model, self.store_path, urlparse(self.model).scheme)
        model.draft_model = self.draft_model
        return model

    def create_api_transport(self) -> APITransport:
        scheme = self.model.split("://", 1)[0]
        return APITransport(self.pruned_model, provider=get_chat_provider(scheme))


def _has_explicit_transport_prefix(model: str) -> bool:
    return _detect_prefixed_transport(model) is not None


def _warn_implicit_default_transport(model: str, *, is_transport_set: bool | None = None) -> None:
    global _default_transport_warned
    if _default_transport_warned:
        return
    if DEFAULT_TRANSPORT != "ollama":
        return
    if is_transport_set is None:
        is_transport_set = get_config().is_set("transport")
    if is_transport_set or _has_explicit_transport_prefix(model):
        return
    with _default_transport_warned_lock:
        if _default_transport_warned:
            return
        warnings.warn(
            "Defaulting to 'ollama' transport is deprecated and will change in a future release. "
            "See https://github.com/containers/ramalama?tab=readme-ov-file#default-transport",
            FutureWarning,
            stacklevel=2,
        )
        # Keep the write colocated with warning emission in the same critical section.
        # Tests use _set_default_transport_warned() to reset this flag safely.
        _default_transport_warned = True


def New(name, args, transport: str | None = None) -> CLASS_MODEL_TYPES:
    if transport is None:
        cfg = get_config()
        transport = cfg.transport
        _warn_implicit_default_transport(name, is_transport_set=cfg.is_set("transport"))
    return TransportFactory(name, args, transport=transport).create()
