import subprocess
import tempfile
import warnings
from unittest.mock import Mock, patch

import pytest

from ramalama.arg_types import StoreArgs
from ramalama.transports.rlcr import RamalamaContainerRegistry, find_model_file_in_image


@pytest.fixture(autouse=True)
def suppress_rlcr_warnings():
    """Suppress expected warnings from RLCR model file discovery during tests"""
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message="Could not find model file in image metadata. Using default model location"
        )
        yield


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
        assert rlcr_model.model == "rlcr.io/ramalama/gemma3-270m:latest"
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
            mock_run.assert_called_once_with(
                [
                    "podman",
                    "image",
                    "inspect",
                    "--format={{index .Config.Labels \"com.ramalama.model.file.location\"}}",
                    "rlcr.io/ramalama/test-model",
                ]
            )

    def test_find_model_file_with_no_value_label(self):
        """Test finding model file when label returns '<no value>'"""
        mock_result_label = Mock()
        mock_result_label.stdout.decode.return_value = "<no value>"

        mock_result_ls = Mock()
        mock_result_ls.stdout.decode.return_value = "model1.gguf\nmodel2.txt\nmodel3.gguf"

        with patch('ramalama.transports.rlcr.run_cmd', side_effect=[mock_result_label, mock_result_ls]) as mock_run:
            result = find_model_file_in_image("podman", "rlcr.io/ramalama/test-model")

            assert result == "model1.gguf"
            assert mock_run.call_count == 2

    def test_find_model_file_label_fails(self):
        """Test fallback when label inspection fails"""
        with patch(
            'ramalama.transports.rlcr.run_cmd', side_effect=subprocess.CalledProcessError(1, "inspect")
        ) as mock_run:
            result = find_model_file_in_image("docker", "rlcr.io/ramalama/test-model")

            assert result is None
            assert mock_run.call_count == 2  # Both label inspection and fallback ls command fail


class TestRLCRIntegration:
    """Integration tests combining multiple components"""

    def test_complete_initialization_flow(self, rlcr_model):
        """Test complete RLCR initialization and model path construction"""
        # Test the complete flow
        assert rlcr_model.model == "rlcr.io/ramalama/gemma3-270m:latest"
        assert rlcr_model._model_type == 'oci'
        assert rlcr_model.conman == "podman"

    @pytest.mark.parametrize(
        "input_model,expected_path",
        [
            ("simple-model", "rlcr.io/ramalama/simple-model:latest"),
            ("model-with-tag:v1.0", "rlcr.io/ramalama/model-with-tag:v1.0"),
            ("namespace/model", "rlcr.io/ramalama/namespace/model:latest"),
            ("complex-name_123:latest", "rlcr.io/ramalama/complex-name_123:latest"),
        ],
    )
    def test_model_path_construction_variations(self, input_model, expected_path):
        """Test various model name inputs result in correct rlcr.io paths"""
        rlcr = RamalamaContainerRegistry(
            model=input_model, model_store_path="/tmp", conman="podman", ignore_stderr=False
        )
        assert rlcr.model == expected_path
