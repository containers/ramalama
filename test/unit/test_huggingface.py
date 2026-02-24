from dataclasses import dataclass

import pytest

import ramalama.common as common_module
import ramalama.transports.huggingface as huggingface_module
from ramalama.transports.huggingface import Huggingface


@dataclass
class PushArgs:
    store: str


def test_push_raises_not_implemented_when_hf_cli_unavailable(tmp_path, monkeypatch):
    huggingface_module.has_hf_cli.cache_clear()
    model = Huggingface("ibm-granite/granite-3b-code-base.Q4_K_M.gguf", str(tmp_path))
    args = PushArgs(store=str(tmp_path))
    monkeypatch.setattr(huggingface_module, "available", lambda _: False, raising=False)
    monkeypatch.setattr(common_module, "available", lambda _: False)

    with pytest.raises(NotImplementedError, match="huggingface-cli"):
        model.push(None, args)
