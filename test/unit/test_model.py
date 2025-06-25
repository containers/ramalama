import socket
from argparse import Namespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from ramalama.model import compute_serving_port
from ramalama.model_factory import ModelFactory


class ARGS:
    store = "/tmp/store"
    engine = ""
    container = True


hf_granite_blob = "https://huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob"
ms_granite_blob = "https://modelscope.cn/models/ibm-granite/granite-3b-code-base-2k-GGUF/file/view"


@pytest.mark.parametrize(
    "model_input,expected_name,expected_tag,expected_orga",
    [
        ("huggingface://granite-code", "granite-code", "latest", ""),
        ("hf://granite-code", "granite-code", "latest", ""),
        (
            f"{hf_granite_blob}/main/granite-3b-code-base.Q4_K_M.gguf",
            "granite-3b-code-base.Q4_K_M.gguf",
            "main",
            "huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF",
        ),
        (
            f"{hf_granite_blob}/8ee52dc636b27b99caf046e717a87fb37ad9f33e/granite-3b-code-base.Q4_K_M.gguf",
            "granite-3b-code-base.Q4_K_M.gguf",
            "8ee52dc636b27b99caf046e717a87fb37ad9f33e",
            "huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF",
        ),
        ("modelscope://granite-code", "granite-code", "latest", ""),
        ("ms://granite-code", "granite-code", "latest", ""),
        (
            f"{ms_granite_blob}/master/granite-3b-code-base.Q4_K_M.gguf",
            "granite-3b-code-base.Q4_K_M.gguf",
            "master",
            "modelscope.cn/models/ibm-granite/granite-3b-code-base-2k-GGUF",
        ),
        (
            f"{ms_granite_blob}/f823b84ec4b84f9a6742c8a1f6a893deeca75f06/granite-3b-code-base.Q4_K_M.gguf",
            "granite-3b-code-base.Q4_K_M.gguf",
            "f823b84ec4b84f9a6742c8a1f6a893deeca75f06",
            "modelscope.cn/models/ibm-granite/granite-3b-code-base-2k-GGUF",
        ),
        ("ollama://granite-code", "granite-code", "latest", ""),
        (
            "https://ollama.com/huihui_ai/granite3.1-dense-abliterated:2b-instruct-fp16",
            "granite3.1-dense-abliterated",
            "2b-instruct-fp16",
            "ollama.com/huihui_ai",
        ),
        ("ollama.com/library/granite-code", "granite-code", "latest", ""),
        (
            "huihui_ai/granite3.1-dense-abliterated:2b-instruct-fp16",
            "granite3.1-dense-abliterated",
            "2b-instruct-fp16",
            "huihui_ai",
        ),
        ("oci://granite-code", "granite-code", "latest", ""),
        ("docker://granite-code", "granite-code", "latest", ""),
        ("docker://granite-code:v1.1.1", "granite-code", "v1.1.1", ""),
        (
            "file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf",
            "granite-3b-code-base.Q4_K_M.gguf",
            "latest",
            "tmp/models",
        ),
    ],
)
def test_extract_model_identifiers(model_input: str, expected_name: str, expected_tag: str, expected_orga: str):
    args = ARGS()
    args.engine = "podman"
    name, tag, orga = ModelFactory(model_input, args).create().extract_model_identifiers()
    assert name == expected_name
    assert tag == expected_tag
    assert orga == expected_orga


@pytest.mark.parametrize(
    "inputPort,expectedRandomizedResult,expectedRandomPortsAvl,expectedOutput,expectedErr",
    [
        ("", [], [None], "8999", IOError),
        ("8999", [], [None], "8999", None),
        ("8080", [8080, 8087, 8085, 8086, 8084, 8090, 8088, 8089, 8082, 8081, 8083], [None], "8080", None),
        (
            "8080",
            [8080, 8088, 8090, 8084, 8081, 8087, 8085, 8089, 8082, 8086, 8083],
            [OSError, None],
            "8088",
            None,
        ),
        (
            "8080",
            [8080, 8090, 8082, 8084, 8088, 8089, 8087, 8081, 8083, 8086, 8085],
            [OSError, OSError, None],
            "8082",
            None,
        ),
        (
            "8080",
            [8080, 8085, 8090, 8081, 8084, 8088, 8086, 8087, 8083, 8082, 8089],
            [OSError, OSError, OSError, OSError, OSError, OSError, OSError, OSError, OSError, OSError, OSError],
            "0",
            IOError,
        ),
    ],
)
def test_compute_serving_port(
    inputPort: str, expectedRandomizedResult: list, expectedRandomPortsAvl: list, expectedOutput: str, expectedErr
):
    args = Namespace(port=inputPort, debug=False, api="")
    mock_socket = socket.socket
    mock_socket.bind = MagicMock(side_effect=expectedRandomPortsAvl)
    mock_compute_ports = Mock(return_value=expectedRandomizedResult)

    with patch('ramalama.model.compute_ports', mock_compute_ports):
        with patch('socket.socket', mock_socket):
            if expectedErr:
                with pytest.raises(expectedErr):
                    outputPort = compute_serving_port(args, False)
                    assert outputPort == expectedOutput
            else:
                outputPort = compute_serving_port(args, False)
                assert outputPort == expectedOutput
