import os
import subprocess
import tempfile
import warnings
from unittest.mock import Mock, patch

import pytest

from ramalama.arg_types import StoreArgs
from ramalama.transports.oci_artifact import download_oci_artifact
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
        args_obj.quiet = False
        args_obj.tlsverify = True
        args_obj.authfile = None
        args_obj.username = None
        args_obj.password = None
        args_obj.passwordstdin = False
        args_obj.REGISTRY = None
        args_obj.verify = True
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


class TestRLCRArtifactFallback:
    def test_pull_falls_back_to_artifact(self, rlcr_model, args):
        args.quiet = False

        def run_cmd_side_effect(cmd, *cmd_args, **cmd_kwargs):
            if len(cmd) >= 2 and cmd[1] == "pull":
                raise subprocess.CalledProcessError(125, cmd)
            mock_result = Mock()
            mock_result.stdout.decode.return_value = ""
            return mock_result

        with patch('ramalama.transports.oci.run_cmd', side_effect=run_cmd_side_effect):
            with patch('ramalama.transports.rlcr.download_oci_artifact', return_value=True) as mock_download:
                rlcr_model.pull(args)
                mock_download.assert_called_once()

    def test_pull_re_raises_when_artifact_download_fails(self, rlcr_model, args):
        def run_cmd_side_effect(cmd, *cmd_args, **cmd_kwargs):
            if len(cmd) >= 2 and cmd[1] == "pull":
                raise subprocess.CalledProcessError(125, cmd)
            mock_result = Mock()
            mock_result.stdout.decode.return_value = ""
            return mock_result

        with patch('ramalama.transports.oci.run_cmd', side_effect=run_cmd_side_effect):
            with patch('ramalama.transports.rlcr.download_oci_artifact', return_value=False):
                with pytest.raises(subprocess.CalledProcessError):
                    rlcr_model.pull(args)


class TestOCIArtifactDownload:
    def test_download_oci_artifact_creates_snapshot(self, rlcr_model, args):
        args.verify = False  # skip model verification for synthetic data
        store = rlcr_model.model_store
        digest = "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"

        class FakeClient:
            def __init__(self, registry, repository, reference, verify_tls, username, password):
                self.registry = registry
                self.repository = repository
                self.reference = reference

            def get_manifest(self):
                manifest = {
                    "artifactType": "application/vnd.ramalama.model.gguf",
                    "blobs": [
                        {
                            "mediaType": "application/octet-stream",
                            "digest": digest,
                            "size": 4,
                            "annotations": {"org.opencontainers.image.title": "model.gguf"},
                        }
                    ],
                }
                return manifest, "sha256:feedfacefeedfacefeedfacefeedfacefeedfacefeedfacefeedfacefeedface"

            def download_blob(self, blob_digest, dest_path):
                assert blob_digest == digest
                data = b"test"
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with open(dest_path, "wb") as fh:
                    fh.write(data)

        with patch('ramalama.transports.oci_artifact.OCIRegistryClient', FakeClient):
            result = download_oci_artifact(
                registry="rlcr.io",
                reference="ramalama/gemma3-270m:gguf",
                model_store=store,
                model_tag=rlcr_model.model_tag,
                args=args,
            )

        assert result is True
        ref = store.get_ref_file(rlcr_model.model_tag)
        assert ref is not None
        model_files = ref.model_files
        assert model_files
        assert model_files[0].name == "model.gguf"

        new_model = RamalamaContainerRegistry(
            model="gemma3-270m", model_store_path=args.store, conman="podman", ignore_stderr=False
        )
        assert new_model.exists()
        assert new_model._artifact_downloaded is True
        assert new_model._get_entry_model_path(True, False, False) == "/mnt/models/gemma-3-270m-it-Q6_K.gguf"
