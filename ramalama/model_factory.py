from typing import Union
from urllib.parse import urlparse

from ramalama.common import rm_until_substring
from ramalama.huggingface import Huggingface
from ramalama.model import MODEL_TYPES
from ramalama.oci import OCI
from ramalama.ollama import Ollama
from ramalama.url import URL


class ModelFactory:

    def __init__(self, model: str, transport: str = "ollama", engine: str = "podman", ignore_stderr: bool = False):
        self.model = model
        self.transport = transport
        self.engine = engine
        self.ignore_stderr = ignore_stderr

    def prune_model_input(self, cls: type[Union[Huggingface, Ollama, OCI, URL]]) -> str:
        # remove protocol from model input
        pruned_model_input = rm_until_substring(self.model, "://")

        if cls == Huggingface:
            pruned_model_input = rm_until_substring(pruned_model_input, "hf.co/")
        elif cls == Ollama:
            pruned_model_input = rm_until_substring(pruned_model_input, "ollama.com/library/")

        return pruned_model_input

    def validate_oci_model_input(self):
        if self.model.startswith("oci://") or self.model.startswith("docker://"):
            return

        for t in MODEL_TYPES:
            if self.model.startswith(t + "://"):
                raise ValueError(f"{self.model} invalid: Only OCI Model types supported")

    def create_huggingface(self) -> Huggingface:
        return Huggingface(self.prune_model_input(Huggingface))

    def create_ollama(self) -> Ollama:
        return Ollama(self.prune_model_input(Ollama))

    def create_oci(self) -> OCI:
        self.validate_oci_model_input()
        return OCI(self.prune_model_input(OCI), self.engine, self.ignore_stderr)

    def create_url(self) -> URL:
        return URL(self.prune_model_input(URL), urlparse(self.model).scheme)

    def create(self) -> Union[Huggingface, Ollama, OCI, URL]:
        if self.model.startswith("huggingface://") or self.model.startswith("hf://") or self.model.startswith("hf.co/"):
            return self.create_huggingface()
        if self.model.startswith("ollama://") or "ollama.com/library/" in self.model:
            return self.create_ollama()
        if self.model.startswith("oci://") or self.model.startswith("docker://"):
            return self.create_oci()
        if self.model.startswith("http://") or self.model.startswith("https://") or self.model.startswith("file://"):
            return self.create_url()

        if self.transport == "huggingface":
            return self.create_huggingface()
        if self.transport == "ollama":
            return self.create_ollama()
        if self.transport == "oci":
            return self.create_oci()

        raise KeyError(f'transport "{self.transport}" not supported. Must be oci, huggingface, or ollama.')
