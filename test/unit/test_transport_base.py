import socket
from argparse import Namespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from ramalama.command.factory import assemble_command
from ramalama.common import MNT_DIR
from ramalama.config import DEFAULT_PORT, DEFAULT_PORT_RANGE
from ramalama.transports.base import Transport, compute_ports, compute_serving_port
from ramalama.transports.oci import OCI
from ramalama.transports.transport_factory import TransportFactory


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
    name, tag, orga = TransportFactory(model_input, args).create().extract_model_identifiers()
    assert name == expected_name
    assert tag == expected_tag
    assert orga == expected_orga


def test_compute_ports():
    res = compute_ports()
    assert type(res) is list
    assert len(res) == (DEFAULT_PORT_RANGE[1] + 1 - DEFAULT_PORT_RANGE[0])
    for port in range(DEFAULT_PORT_RANGE[0], DEFAULT_PORT_RANGE[1] + 1):
        assert port in res


@pytest.mark.parametrize(
    "exclude,count,first",
    [
        (None, 101, DEFAULT_PORT),
        ([], 101, DEFAULT_PORT),
        ([str(DEFAULT_PORT)], 100, DEFAULT_PORT + 1),
        ([str(DEFAULT_PORT), str(DEFAULT_PORT + 1)], 99, DEFAULT_PORT + 2),
        (list(map(str, range(*DEFAULT_PORT_RANGE))), 1, DEFAULT_PORT_RANGE[1]),
    ],
)
def test_compute_ports_exclude(exclude: list, count: int, first: int):
    res = compute_ports(exclude=exclude)
    assert len(res) == count
    assert res[0] == first
    for port in exclude or []:
        assert port not in res


@pytest.mark.parametrize(
    "inputPort,expectedRandomizedResult,expectedRandomPortsAvl,expectedOutput,expectedErr",
    [
        ("", [], [None], "8999", IOError),
        (None, [], [None], "8080", IOError),
        ("8999", [], [None], "8999", None),
        ("8080", [8080, 8087, 8085, 8086, 8084, 8090, 8088, 8089, 8082, 8081, 8083], [None], "8080", None),
        (
            "8080",
            [8080, 8088, 8090, 8084, 8081, 8087, 8085, 8089, 8082, 8086, 8083],
            [OSError, None],
            "8080",
            None,
        ),
        (
            "8085",
            [8080, 8090, 8082, 8084, 8088, 8089, 8087, 8081, 8083, 8086, 8085],
            [OSError, OSError, None],
            "8085",
            None,
        ),
    ],
)
def test_compute_serving_port(
    inputPort: str,
    expectedRandomizedResult: list,
    expectedRandomPortsAvl: list,
    expectedOutput: str,
    expectedErr,
):
    args = Namespace(port=inputPort, debug=False, api="")
    # Set port_override if user specified a port (not empty or None)
    if inputPort and inputPort != "":
        args.port_override = True

    mock_socket = socket.socket
    mock_socket.bind = MagicMock(side_effect=expectedRandomPortsAvl)
    mock_compute_ports = Mock(return_value=expectedRandomizedResult)

    with patch('ramalama.transports.base.compute_ports', mock_compute_ports):
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

    @patch('ramalama.transports.base.platform.system')
    @patch('ramalama.transports.base.platform.machine')
    def test_mlx_validation_container_no_error(self, mock_machine, mock_system):
        """Test that MLX runtime validation passes when mocking macOS with Apple Silicon"""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"

        args = Namespace(runtime="mlx", container=True)

        model = Transport("test-model", "/tmp/store")

        # Should not raise an error since we're mocking macOS with Apple Silicon
        model.validate_args(args)

    @patch('ramalama.transports.base.platform.system')
    @patch('ramalama.transports.base.platform.machine')
    def test_mlx_validation_non_macos_error(self, mock_machine, mock_system):
        """Test that MLX runtime fails on non-macOS systems"""
        mock_system.return_value = "Linux"
        mock_machine.return_value = "x86_64"

        args = Namespace(runtime="mlx", container=False, privileged=False)

        model = Transport("test-model", "/tmp/store")

        with pytest.raises(ValueError, match="MLX runtime is only supported on macOS"):
            model.validate_args(args)

    @patch('ramalama.transports.base.platform.system')
    @patch('ramalama.transports.base.platform.machine')
    def test_mlx_validation_success(self, mock_machine, mock_system):
        """Test that MLX runtime passes validation on macOS with --nocontainer"""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"

        args = Namespace(runtime="mlx", container=False, privileged=False)

        model = Transport("test-model", "/tmp/store")

        # Should not raise any exception
        model.validate_args(args)

    @patch('ramalama.transports.base.platform.system')
    @patch('ramalama.transports.base.platform.machine')
    @patch('ramalama.transports.base.Transport.serve_nonblocking', return_value=MagicMock())
    @patch('ramalama.chat.chat')
    @patch('socket.socket')
    def test_mlx_run_uses_server_client_model(
        self, mock_socket_class, mock_chat, mock_serve_nonblocking, mock_machine, mock_system
    ):
        """Test that MLX runtime uses server-client model in run method"""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"

        # Mock socket to simulate successful connection (server ready)
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 0  # Successful connection
        mock_socket.__enter__.return_value = mock_socket
        mock_socket.__exit__.return_value = False
        mock_socket_class.return_value = mock_socket

        # Add all required arguments for the run method
        args = Namespace(
            subcommand="run",
            runtime="mlx",
            container=False,
            privileged=False,
            debug=False,
            MODEL="test-model",
            ARGS=None,  # No prompt arguments
            pull="missing",  # Required for get_model_path
            dryrun=True,  # use dryrun to avoid file system checks
            store="/tmp/store",
            port="8080",
            engine="podman",
        )

        model = Transport(args.MODEL, args.store)
        cmd = assemble_command(args)

        with patch.object(model, 'get_container_name', return_value="test-container"):
            with patch('sys.stdin.isatty', return_value=True):  # Mock tty for interactive mode
                model.run(args, cmd)

        # Verify that serve_nonblocking was called (indicating server-client model)
        mock_serve_nonblocking.assert_called_once()

        # Verify that chat.chat was called (parent process)
        mock_chat.assert_called_once()

        # Verify args were set up correctly for server-client model
        # MLX runtime uses OpenAI-compatible endpoints under /v1
        assert args.url == "http://127.0.0.1:8080/v1"


class TestOCIModelSetupMounts:
    """Test the OCI model setup_mounts functionality that was refactored"""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock engine for testing"""
        engine = Mock()
        engine.use_podman = True
        engine.add = Mock()
        return engine

    @pytest.fixture
    def oci_model(self):
        """Create an OCI model for testing"""
        model = OCI("test-registry.io/test-model:latest", "/tmp/store", "podman")
        return model

    def test_setup_mounts_dryrun(self, oci_model, mock_engine):
        """Test that setup_mounts returns early on dryrun"""
        args = Namespace(dryrun=True)
        oci_model.engine = mock_engine

        result = oci_model.setup_mounts(args)

        assert result is None
        mock_engine.add.assert_not_called()

    def test_setup_mounts_oci_podman(self, oci_model, mock_engine):
        """Test OCI model mounting with Podman (image mount)"""
        args = Namespace(dryrun=False)
        mock_engine.use_podman = True
        oci_model.engine = mock_engine

        oci_model.setup_mounts(args)

        expected_mount = f"--mount=type=image,src={oci_model.model},destination={MNT_DIR},subpath=/models,rw=false"
        mock_engine.add.assert_called_once_with([expected_mount])

    @patch('ramalama.transports.base.populate_volume_from_image')
    def test_setup_mounts_oci_docker(self, mock_populate_volume, oci_model, mock_engine):
        """Test OCI model mounting with Docker (volume mount using populate_volume_from_image)"""
        args = Namespace(dryrun=False, container=True, generate=False, engine="docker")
        mock_engine.use_podman = False
        mock_engine.use_docker = True
        oci_model.engine = mock_engine

        mock_volume_name = "ramalama-models-abc123"
        mock_populate_volume.return_value = mock_volume_name

        oci_model.setup_mounts(args)

        # Verify populate_volume_from_image was called
        mock_populate_volume.assert_called_once()
        call_args = mock_populate_volume.call_args
        assert call_args[0][0] == oci_model  # model argument
        assert call_args[0][1] is args

        # Verify mount command was added
        expected_mount = f"--mount=type=volume,src={mock_volume_name},dst={MNT_DIR},readonly"
        mock_engine.add.assert_called_once_with([expected_mount])
