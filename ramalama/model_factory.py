from typing import Union

from ramalama.huggingface import Huggingface
from ramalama.oci import OCI
from ramalama.ollama import Ollama
from ramalama.url import URL


class ModelFactory:

    def __init__(self, model: str, transport: str = "ollama", engine: str = "podman"):
        self.model = model
        self.transport = transport
        self.engine = engine

    def create(self) -> Union[Huggingface, Ollama, OCI, URL]:
        if self.model.startswith("huggingface://") or self.model.startswith("hf://") or self.model.startswith("hf.co/"):
            return Huggingface(self.model)
        if self.model.startswith("ollama://") or "ollama.com/library/" in self.model:
            return Ollama(self.model)
        if self.model.startswith("oci://") or self.model.startswith("docker://"):
            return OCI(self.model, self.engine)
        if self.model.startswith("http://") or self.model.startswith("https://") or self.model.startswith("file://"):
            return URL(self.model)

        if self.transport == "huggingface":
            return Huggingface(self.model)
        if self.transport == "ollama":
            return Ollama(self.model)
        if self.transport == "oci":
            return OCI(self.model, self.engine)

        raise KeyError(f'transport "{self.transport}" not supported. Must be oci, huggingface, or ollama.')
