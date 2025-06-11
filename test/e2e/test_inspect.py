import re
from test.e2e.utils import RamalamaExecWorkspace

import pytest


@pytest.mark.e2e
def test_inspect_gguf_model():
    with RamalamaExecWorkspace() as ctx:
        # Pull tiny model
        ctx.check_call(["ramalama", "pull", "tiny"])

        pattern = (
            "tinyllama\n"
            "   Path: .*store/ollama/tinyllama/.*\n"
            "   Registry: ollama\n"
            "   Format: GGUF\n"
            "   Version: 3\n"
            "   Endianness: little\n"
            "   Metadata: 23 entries\n"
            "   Tensors: 201 entries\n"
        )
        result = ctx.check_output(["ramalama", "inspect", "tiny"])
        assert re.search(pattern, result)


@pytest.mark.e2e
def test_inspect_gguf_model_with_all_flag():
    with RamalamaExecWorkspace() as ctx:
        # Pull tiny model
        ctx.check_call(["ramalama", "pull", "tiny"])

        pattern = (
            "tinyllama\n"
            "   Path: .*store/ollama/tinyllama/.*\n"
            "   Registry: ollama\n"
            "   Format: GGUF\n"
            "   Version: 3\n"
            "   Endianness: little\n"
            "   Metadata: \n"
            "      general.architecture: llama\n"
        )
        result = ctx.check_output(["ramalama", "inspect", "--all", "tiny"])
        assert re.search(pattern, result)
