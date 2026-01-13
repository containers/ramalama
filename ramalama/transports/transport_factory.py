import copy
from collections.abc import Callable
from typing import TypeAlias
from urllib.parse import urlparse

from ramalama.arg_types import StoreArgType
from ramalama.chat_providers.api_providers import get_chat_provider
from ramalama.common import rm_until_substring
from ramalama.config import get_config
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


class TransportFactory:
    def __init__(
        self,
        model: str,
        args: StoreArgType,
        transport: str = "ollama",
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
        match self.model:
            case model if model.startswith(("huggingface://", "hf://", "hf.co/")):
                return Huggingface, self.create_huggingface
            case model if model.startswith(("modelscope://", "ms://")):
                return ModelScope, self.create_modelscope
            case model if model.startswith(("ollama://", "ollama.com/library/")):
                return Ollama, self.create_ollama
            case model if model.startswith(("oci://", "docker://")):
                return OCI, self.create_oci
            case model if model.startswith("rlcr://"):
                return RamalamaContainerRegistry, self.create_rlcr
            case model if model.startswith(("http://", "https://", "file:")):
                return URL, self.create_url
            case model if model.startswith(("openai://")):
                return APITransport, self.create_api_transport

        match self.transport:
            case "huggingface":
                return Huggingface, self.create_huggingface
            case "modelscope":
                return ModelScope, self.create_modelscope
            case "ollama":
                return Ollama, self.create_ollama
            case "rlcr":
                return RamalamaContainerRegistry, self.create_rlcr
            case "oci":
                return OCI, self.create_oci

        raise KeyError(f'transport "{self.transport}" not supported. Must be oci, huggingface, modelscope, or ollama.')

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


def New(name, args, transport: str | None = None) -> CLASS_MODEL_TYPES:
    if transport is None:
        transport = get_config().transport
    return TransportFactory(name, args, transport=transport).create()
