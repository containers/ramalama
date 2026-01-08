from .huggingface import Huggingface, HuggingfaceRepository
from .modelscope import ModelScope, ModelScopeRepository
from .oci.oci import OCI
from .ollama import Ollama, OllamaRepository
from .rlcr import RamalamaContainerRegistry
from .url import URL
from .api import APITransport

__all__ = [
    "api",
    "huggingface",
    "modelscope",
    "ollama",
    "rlcr",
    "url",
    "Huggingface",
    "HuggingfaceRepository",
    "ModelScope",
    "ModelScopeRepository",
    "OCI",
    "Ollama",
    "OllamaRepository",
    "RamalamaContainerRegistry",
    "URL",
    "APITransport",
]
