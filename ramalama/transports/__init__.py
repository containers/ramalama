from ramalama.api_provider_specs import DEFAULT_API_PROVIDER_SPECS, APIProviderSpec

from .api import APITransport
from .huggingface import Huggingface, HuggingfaceRepository
from .modelscope import ModelScope, ModelScopeRepository
from .oci import OCI
from .ollama import Ollama, OllamaRepository
from .rlcr import RamalamaContainerRegistry
from .url import URL

__all__ = [
    "Huggingface",
    "HuggingfaceRepository",
    "APITransport",
    "APIProviderSpec",
    "DEFAULT_API_PROVIDER_SPECS",
    "ModelScope",
    "ModelScopeRepository",
    "OCI",
    "Ollama",
    "OllamaRepository",
    "RamalamaContainerRegistry",
    "URL",
]
