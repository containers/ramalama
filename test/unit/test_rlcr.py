import subprocess
import tempfile
import warnings
from dataclasses import dataclass
from unittest.mock import MagicMock, Mock, patch

import pytest

from ramalama.arg_types import StoreArgs
from ramalama.common import MNT_DIR
from ramalama.transports.rlcr import RamalamaContainerRegistry, find_model_file_in_image


@pytest.fixture(autouse=True)
def suppress_rlcr_warnings():
    """Suppress expected warnings from RLCR model file discovery during tests"""
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message="Could not find model file in image metadata. Using default model location"
        )
        yield


@dataclass
class MockEngine:
    use_podman: bool = True

    def __init__(self, use_podman: bool = True):
        self.use_podman = use_podman
        self.commands = []

    def add(self, commands):
        self.commands.extend(commands)


@pytest.fixture
def args():
    with tempfile.TemporaryDirectory() as tmpdir:
        args_obj = StoreArgs(store=tmpdir, engine="podman", container=True)
        args_obj.dryrun = False  # Add dryrun attribute dynamically
        yield args_obj


@pytest.fixture
def rlcr_model(args):
    return RamalamaContainerRegistry(
        model="gemma3-270m", model_store_path=args.store, conman="podman", ignore_stderr=False
    )


@pytest.fixture
def rlcr_model_docker(args):
    return RamalamaContainerRegistry(
        model="gemma3-270m", model_store_path=args.store, conman="docker", ignore_stderr=False
    )


class TestRLCRInitialization:
    """Test RLCR model initialization and model path construction"""

    def test_rlcr_model_initialization(self, rlcr_model):
        """Test that RLCR model initializes with correct rlcr.io prefix"""
        assert rlcr_model.model == "rlcr.io/ramalama/gemma3-270m"
        assert rlcr_model._model_type == 'oci'
        assert rlcr_model.conman == "podman"

    def test_rlcr_inherits_from_oci(self, rlcr_model):
        """Test that RLCR properly inherits from OCI"""
        from ramalama.transports.oci import OCI

        assert isinstance(rlcr_model, OCI)


class TestModelFileDiscovery:
    """Test the model file discovery functionality"""

    def test_find_model_file_with_label_success(self):
        """Test finding model file using container label"""
        mock_result = Mock()
        mock_result.stdout.decode.return_value = "gemma3-270m.gguf"

        with patch('ramalama.transports.rlcr.run_cmd', return_value=mock_result) as mock_run:
            result = find_model_file_in_image("podman", "rlcr.io/ramalama/test-model")

            assert result == "gemma3-270m.gguf"
            mock_run.assert_called_once_with([
                "podman",
                "image",
                "inspect",
                "--format={{index .Config.Labels \"com.ramalama.model.file.location\"}}",
                "rlcr.io/ramalama/test-model",
            ])

    def test_find_model_file_with_no_value_label(self):
        """Test finding model file when label returns '<no value>'"""
        mock_result_label = Mock()
        mock_result_label.stdout.decode.return_value = "<no value>"

        with (
            patch('ramalama.transports.rlcr.run_cmd', return_value=mock_result_label) as mock_run,
            patch('warnings.warn') as mock_warn,
        ):
            result = find_model_file_in_image("podman", "rlcr.io/ramalama/test-model")

            assert result == "/models/model.file"
            assert mock_run.call_count == 1
            mock_warn.assert_called_once_with(
                "Could not find model file in image metadata. Using default model location"
            )

            # Check only the label inspection was called
            mock_run.assert_called_once_with([
                "podman",
                "image",
                "inspect",
                "--format={{index .Config.Labels \"com.ramalama.model.file.location\"}}",
                "rlcr.io/ramalama/test-model",
            ])

    def test_find_model_file_label_fails(self):
        """Test fallback to default when label inspection fails"""
        with (
            patch(
                'ramalama.transports.rlcr.run_cmd', side_effect=subprocess.CalledProcessError(1, "inspect")
            ) as mock_run,
            patch('warnings.warn') as mock_warn,
        ):
            result = find_model_file_in_image("docker", "rlcr.io/ramalama/test-model")

            assert result == "/models/model.file"
            assert mock_run.call_count == 1
            mock_warn.assert_called_once_with(
                "Could not find model file in image metadata. Using default model location"
            )


class TestSetupMounts:
    """Test the setup_mounts method for both Podman and Docker"""

    def test_setup_mounts_dryrun(self, rlcr_model, args):
        """Test that setup_mounts returns early on dryrun"""
        args.dryrun = True
        result = rlcr_model.setup_mounts(args)
        assert result is None

    def test_setup_mounts_podman_engine(self, rlcr_model, args):
        """Test Podman mounting logic"""
        args.dryrun = False
        mock_engine = MockEngine(use_podman=True)
        rlcr_model.engine = mock_engine

        rlcr_model.setup_mounts(args)

        expected_commands = [
            f"--mount=type=image,src=rlcr.io/ramalama/gemma3-270m,destination={MNT_DIR},subpath=/models,rw=false"
        ]
        assert rlcr_model.engine.commands == expected_commands

    @patch('subprocess.Popen')
    @patch('ramalama.transports.rlcr.run_cmd')
    def test_setup_mounts_docker_engine(self, mock_run_cmd, mock_popen, rlcr_model_docker, args):
        """Test Docker mounting logic"""
        args.dryrun = False
        mock_engine = MockEngine(use_podman=False)
        rlcr_model_docker.engine = mock_engine

        # Mock the Popen processes for export/tar streaming
        mock_export_proc = MagicMock()
        mock_export_proc.stdout = Mock()
        mock_export_proc.wait.return_value = 0
        mock_export_proc.__enter__ = Mock(return_value=mock_export_proc)
        mock_export_proc.__exit__ = Mock(return_value=None)

        mock_tar_proc = MagicMock()
        mock_tar_proc.wait.return_value = 0
        mock_tar_proc.__enter__ = Mock(return_value=mock_tar_proc)
        mock_tar_proc.__exit__ = Mock(return_value=None)

        mock_popen.side_effect = [mock_export_proc, mock_tar_proc]

        rlcr_model_docker.setup_mounts(args)

        # Verify Docker volume operations were called
        assert mock_run_cmd.call_count >= 3  # volume create, rm, create

        # Verify Popen was called twice (export and tar)
        assert mock_popen.call_count == 2

        # Check that a mount command was added to engine
        assert len(rlcr_model_docker.engine.commands) == 1
        mount_cmd = rlcr_model_docker.engine.commands[0]
        assert mount_cmd.startswith("--mount=type=volume,src=ramalama-models-")
        assert f"dst={MNT_DIR},readonly" in mount_cmd


class TestRLCRIntegration:
    """Integration tests combining multiple components"""

    @patch('ramalama.transports.rlcr.find_model_file_in_image')
    def test_complete_podman_flow(self, mock_find_file, rlcr_model, args):
        """Test complete flow for Podman from initialization to mount setup"""
        mock_find_file.return_value = "test-model.gguf"
        rlcr_model.engine = MockEngine(use_podman=True)

        # Test the complete flow
        assert rlcr_model.model == "rlcr.io/ramalama/gemma3-270m"
        assert rlcr_model._model_type == 'oci'

        rlcr_model.setup_mounts(args)

        expected_commands = [
            f"--mount=type=image,src=rlcr.io/ramalama/gemma3-270m,destination={MNT_DIR},subpath=/models,rw=false"
        ]

        assert rlcr_model.engine.commands == expected_commands

    @pytest.mark.parametrize(
        "input_model,expected_path",
        [
            ("simple-model", "rlcr.io/ramalama/simple-model"),
            ("model-with-tag:v1.0", "rlcr.io/ramalama/model-with-tag:v1.0"),
            ("namespace/model", "rlcr.io/ramalama/namespace/model"),
            ("complex-name_123:latest", "rlcr.io/ramalama/complex-name_123:latest"),
        ],
    )
    def test_model_path_construction_variations(self, input_model, expected_path):
        """Test various model name inputs result in correct rlcr.io paths"""
        rlcr = RamalamaContainerRegistry(
            model=input_model, model_store_path="/tmp", conman="podman", ignore_stderr=False
        )
        assert rlcr.model == expected_path
