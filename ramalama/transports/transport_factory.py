import copy
from collections.abc import Callable
from typing import TypeAlias
from urllib.parse import urlparse

from ramalama.arg_types import StoreArgType
from ramalama.common import rm_until_substring
from ramalama.config import CONFIG
from ramalama.transports.base import MODEL_TYPES
from ramalama.transports.huggingface import Huggingface
from ramalama.transports.modelscope import ModelScope
from ramalama.transports.oci import OCI
from ramalama.transports.ollama import Ollama
from ramalama.transports.rlcr import RamalamaContainerRegistry
from ramalama.transports.url import URL

CLASS_MODEL_TYPES: TypeAlias = Huggingface | Ollama | OCI | URL | ModelScope | RamalamaContainerRegistry


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
        self.draft_model = None

        if getattr(args, 'model_draft', None):
            dm_args = copy.deepcopy(args)
            dm_args.model_draft = None  # type: ignore
            self.draft_model = TransportFactory(args.model_draft, dm_args, ignore_stderr=True).create()  # type: ignore

    def detect_model_model_type(self) -> tuple[type[CLASS_MODEL_TYPES], Callable[[], CLASS_MODEL_TYPES]]:
        for prefix in ["huggingface://", "hf://", "hf.co/"]:
            if self.model.startswith(prefix):
                return Huggingface, self.create_huggingface
        for prefix in ["modelscope://", "ms://"]:
            if self.model.startswith(prefix):
                return ModelScope, self.create_modelscope
        for prefix in ["ollama://", "ollama.com/library/"]:
            if self.model.startswith(prefix):
                return Ollama, self.create_ollama
        for prefix in ["oci://", "docker://"]:
            if self.model.startswith(prefix):
                return OCI, self.create_oci
        if self.model.startswith("rlcr://"):
            return RamalamaContainerRegistry, self.create_rlcr
        for prefix in ["http://", "https://", "file://"]:
            if self.model.startswith(prefix):
                return URL, self.create_url
        if self.transport == "huggingface":
            return Huggingface, self.create_huggingface
        if self.transport == "modelscope":
            return ModelScope, self.create_modelscope
        if self.transport == "ollama":
            return Ollama, self.create_ollama
        if self.transport == "rlcr":
            return RamalamaContainerRegistry, self.create_rlcr
        if self.transport == "oci":
            return OCI, self.create_oci

        raise KeyError(f'transport "{self.transport}" not supported. Must be oci, huggingface, modelscope, or ollama.')

    def prune_model_input(self) -> str:
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


def New(name, args, transport: str | None = None) -> CLASS_MODEL_TYPES:
    if transport is None:
        transport = CONFIG.transport
    return TransportFactory(name, args, transport=transport).create()
