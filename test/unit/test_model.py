import socket
from argparse import Namespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from ramalama.model import Model, compute_serving_port
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
        ("ollama://granite-code", "granite-code", "latest", "library"),
        (
            "https://ollama.com/huihui_ai/granite3.1-dense-abliterated:2b-instruct-fp16",
            "granite3.1-dense-abliterated",
            "2b-instruct-fp16",
            "ollama.com/huihui_ai",
        ),
        ("ollama.com/library/granite-code", "granite-code", "latest", "library"),
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


class TestMLXRuntime:
    """Test MLX runtime functionality"""

    def test_mlx_serve_args(self):
        """Test that MLX serve generates correct arguments"""
        args = Namespace(
            port="8080",
            host="127.0.0.1",
            context=2048,
            temp="0.8",
            runtime_args=["--verbose"],
            container=False,
            generate=False,
            dryrun=True,
        )

        model = Model("test-model", "/tmp/store")

        exec_args = model.mlx_serve(args)

        expected_args = [
            "mlx_lm.server",
            "--model",
            "/path/to/model",
            "--temp",
            "0.8",
            "--max-tokens",
            "2048",
            "--verbose",
            "--port",
            "8080",
            "--host",
            "127.0.0.1",
        ]

        assert exec_args == expected_args

    @patch('ramalama.model.platform.system')
    @patch('ramalama.model.platform.machine')
    def test_mlx_validation_container_no_error(self, mock_machine, mock_system):
        """Test that MLX runtime validation passes when mocking macOS with Apple Silicon"""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"

        args = Namespace(runtime="mlx", container=True)

        model = Model("test-model", "/tmp/store")

        # Should not raise an error since we're mocking macOS with Apple Silicon
        model.validate_args(args)

    @patch('ramalama.model.platform.system')
    @patch('ramalama.model.platform.machine')
    def test_mlx_validation_non_macos_error(self, mock_machine, mock_system):
        """Test that MLX runtime fails on non-macOS systems"""
        mock_system.return_value = "Linux"
        mock_machine.return_value = "x86_64"

        args = Namespace(runtime="mlx", container=False, privileged=False)

        model = Model("test-model", "/tmp/store")

        with pytest.raises(ValueError, match="MLX runtime is only supported on macOS"):
            model.validate_args(args)

    @patch('ramalama.model.platform.system')
    @patch('ramalama.model.platform.machine')
    def test_mlx_validation_success(self, mock_machine, mock_system):
        """Test that MLX runtime passes validation on macOS with --nocontainer"""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"

        args = Namespace(runtime="mlx", container=False, privileged=False)

        model = Model("test-model", "/tmp/store")

        # Should not raise any exception
        model.validate_args(args)

    @patch('ramalama.model.platform.system')
    @patch('ramalama.model.platform.machine')
    @patch('ramalama.model.compute_serving_port')
    @patch('ramalama.model.os.fork')
    @patch('ramalama.chat.chat')
    @patch('socket.socket')
    def test_mlx_run_uses_server_client_model(
        self, mock_socket_class, mock_chat, mock_fork, mock_compute_port, mock_machine, mock_system
    ):
        """Test that MLX runtime uses server-client model in run method"""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"
        mock_compute_port.return_value = "8080"
        mock_fork.return_value = 123  # Parent process

        # Mock socket to simulate successful connection (server ready)
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 0  # Successful connection
        mock_socket.__enter__.return_value = mock_socket
        mock_socket.__exit__.return_value = False
        mock_socket_class.return_value = mock_socket

        # Add all required arguments for the run method
        args = Namespace(
            runtime="mlx",
            container=False,
            privileged=False,
            debug=False,
            MODEL="test-model",
            ARGS=None,  # No prompt arguments
            pull="missing",  # Required for get_model_path
            dryrun=True,  # use dryrun to avoid file system checks
        )

        model = Model("test-model", "/tmp/store")

        with patch.object(model, 'get_container_name', return_value="test-container"):
            with patch('sys.stdin.isatty', return_value=True):  # Mock tty for interactive mode
                model.run(args)

        # Verify that compute_serving_port was called
        mock_compute_port.assert_called_once()

        # Verify that fork was called (indicating server-client model)
        mock_fork.assert_called_once()

        # Verify that chat.chat was called (parent process)
        mock_chat.assert_called_once()

        # Verify args were set up correctly for server-client model
        # MLX runtime should include /v1 in the URL
        assert args.url == "http://127.0.0.1:8080/v1"
        assert args.pid2kill == 123

    @patch('ramalama.model.platform.system')
    @patch('ramalama.model.platform.machine')
    def test_mlx_build_exec_args_includes_server_subcommand(self, mock_machine, mock_system):
        """Test that MLX build_exec_args correctly handles server subcommand"""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"

        args = Namespace(
            temp="0.7", seed=42, context=1024, runtime_args=["--verbose"], container=False, generate=False, dryrun=True
        )

        model = Model("test-model", "/tmp/store")

        # Test that server subcommand is supported
        exec_args = model._build_mlx_exec_args("server", args, ["--port", "8080"])

        expected_args = [
            "mlx_lm.server",
            "--model",
            "/path/to/model",
            "--temp",
            "0.7",
            "--seed",
            "42",
            "--max-tokens",
            "1024",
            "--verbose",
            "--port",
            "8080",
        ]

        assert exec_args == expected_args

    @patch('ramalama.model.platform.system')
    @patch('ramalama.model.platform.machine')
    def test_mlx_benchmarking_not_supported(self, mock_machine, mock_system):
        """Test that MLX runtime raises NotImplementedError for benchmarking"""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"

        args = Namespace(runtime="mlx", MODEL="test-model", container=False, generate=False, dryrun=True)

        model = Model("test-model", "/tmp/store")

        with pytest.raises(NotImplementedError, match="Benchmarking is not supported by the MLX runtime"):
            model.build_exec_args_bench(args)

    @patch('ramalama.model.platform.system')
    @patch('ramalama.model.platform.machine')
    def test_mlx_perplexity_not_supported(self, mock_machine, mock_system):
        """Test that MLX runtime raises NotImplementedError for perplexity"""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"

        args = Namespace(runtime="mlx", MODEL="test-model", container=False, generate=False, dryrun=True)

        model = Model("test-model", "/tmp/store")

        with pytest.raises(NotImplementedError, match="Perplexity calculation is not supported by the MLX runtime"):
            model.build_exec_args_perplexity(args)
