from .huggingface import Huggingface, HuggingfaceRepository
from .modelscope import ModelScope, ModelScopeRepository
from .oci import OCI
from .ollama import Ollama, OllamaRepository
from .rlcr import RamalamaContainerRegistry
from .url import URL

__all__ = [
    "Huggingface",
    "HuggingfaceRepository",
    "ModelScope",
    "ModelScopeRepository",
    "OCI",
    "Ollama",
    "OllamaRepository",
    "RamalamaContainerRegistry",
    "URL",
]
