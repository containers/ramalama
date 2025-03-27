import argparse
from typing import Callable, Tuple, Union
from urllib.parse import urlparse

from ramalama.common import rm_until_substring
from ramalama.huggingface import Huggingface
from ramalama.model import MODEL_TYPES
from ramalama.model_store import GlobalModelStore, ModelStore
from ramalama.oci import OCI
from ramalama.ollama import Ollama
from ramalama.url import URL


class ModelFactory:

    def __init__(
        self,
        model: str,
        args: argparse,
        transport: str = "ollama",
        ignore_stderr: bool = False,
    ):
        self.model = model
        self.store_path = args.store
        self.use_model_store = args.use_model_store
        self.transport = transport
        self.engine = args.engine
        self.ignore_stderr = ignore_stderr
        self.container = args.container

        self.model_cls: type[Union[Huggingface, Ollama, OCI, URL]]
        self.create: Callable[[], Union[Huggingface, Ollama, OCI, URL]]
        self.model_cls, self.create = self.detect_model_model_type()

        self.pruned_model = self.prune_model_input()

    def detect_model_model_type(
        self,
    ) -> Tuple[type[Union[Huggingface, Ollama, OCI, URL]], Callable[[], Union[Huggingface, Ollama, OCI, URL]]]:
        if self.model.startswith("huggingface://") or self.model.startswith("hf://") or self.model.startswith("hf.co/"):
            return Huggingface, self.create_huggingface
        if self.model.startswith("ollama://") or "ollama.com/library/" in self.model:
            return Ollama, self.create_ollama
        if self.model.startswith("oci://") or self.model.startswith("docker://"):
            return OCI, self.create_oci
        if self.model.startswith("http://") or self.model.startswith("https://") or self.model.startswith("file://"):
            return URL, self.create_url

        if self.transport == "huggingface":
            return Huggingface, self.create_huggingface
        if self.transport == "ollama":
            return Ollama, self.create_ollama
        if self.transport == "oci":
            return OCI, self.create_oci

        raise KeyError(f'transport "{self.transport}" not supported. Must be oci, huggingface, or ollama.')

    def prune_model_input(self) -> str:
        # remove protocol from model input
        pruned_model_input = rm_until_substring(self.model, "://")

        if self.model_cls == Huggingface:
            pruned_model_input = rm_until_substring(pruned_model_input, "hf.co/")
        elif self.model_cls == Ollama:
            pruned_model_input = rm_until_substring(pruned_model_input, "ollama.com/library/")

        return pruned_model_input

    def validate_oci_model_input(self):
        if self.model.startswith("oci://") or self.model.startswith("docker://"):
            return

        for t in MODEL_TYPES:
            if self.model.startswith(t + "://"):
                raise ValueError(f"{self.model} invalid: Only OCI Model types supported")

    def set_optional_model_store(self, model: Union[Huggingface, Ollama, OCI, URL]):
        if self.use_model_store:
            name, _, orga = model.extract_model_identifiers()
            model.store = ModelStore(GlobalModelStore(self.store_path), name, type(model).__name__.lower(), orga)

    def create_huggingface(self) -> Huggingface:
        model = Huggingface(self.pruned_model)
        self.set_optional_model_store(model)
        return model

    def create_ollama(self) -> Ollama:
        model = Ollama(self.pruned_model)
        self.set_optional_model_store(model)
        return model

    def create_oci(self) -> OCI:
        if not self.container:
            raise ValueError("OCI containers cannot be used with the --nocontainer option.")

        self.validate_oci_model_input()
        model = OCI(self.pruned_model, self.engine, self.ignore_stderr)
        self.set_optional_model_store(model)
        return model

    def create_url(self) -> URL:
        model = URL(self.pruned_model, urlparse(self.model).scheme)
        self.set_optional_model_store(model)
        return model
