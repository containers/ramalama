import pytest
from ramalama.model_factory import ModelFactory
from ramalama.huggingface import Huggingface
from ramalama.oci import OCI
from ramalama.ollama import Ollama
from ramalama.url import URL

from dataclasses import dataclass

@dataclass
class Input():
    Model: str
    Transport: str
    Engine: str

@pytest.mark.parametrize(
        "input,expected,error", 
        [
            (Input("", "", ""), None, KeyError),
            (Input("huggingface://granite-code", "", ""), Huggingface, None),
            (Input("hf://granite-code", "", ""), Huggingface, None),
            (Input("hf.co/granite-code", "", ""), Huggingface, None),
            (Input("ollama://granite-code", "", ""), Ollama, None),
            (Input("ollama.com/library/granite-code", "", ""), Ollama, None),
            (Input("oci://granite-code", "", "podman"), OCI, None),
            (Input("docker://granite-code", "", "podman"), OCI, None),
            (Input("http://huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf", "", ""), URL, None),
            (Input("https://huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf", "", ""), URL, None),
            (Input("file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf", "", ""), URL, None),
            
            (Input("granite-code", "huggingface", ""), Huggingface, None),
            (Input("granite-code", "ollama", ""), Ollama, None),
            (Input("granite-code", "oci", ""), OCI, None),



        ]
)
def test_model_factory_create(input: Input, expected, error):
    if error is not None:
        with pytest.raises(error):
            ModelFactory(input.Model, input.Transport, input.Engine).create()
    else:
        model = ModelFactory(input.Model, input.Transport, input.Engine).create()
        assert isinstance(model, expected)
