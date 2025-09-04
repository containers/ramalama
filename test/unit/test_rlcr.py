import subprocess
import tempfile
from unittest.mock import Mock, patch, MagicMock, call
from dataclasses import dataclass

import pytest

from ramalama.arg_types import StoreArgs
from ramalama.model_store.stores.rlcr import RamalamaContainerRegistry, find_model_file_in_image
from ramalama.common import MNT_DIR


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
        model="gemma3-270m",
        model_store_path=args.store,
        conman="podman",
        ignore_stderr=False
    )


@pytest.fixture
def rlcr_model_docker(args):
    return RamalamaContainerRegistry(
        model="gemma3-270m",
        model_store_path=args.store,
        conman="docker",
        ignore_stderr=False
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
        from ramalama.oci import OCI
        assert isinstance(rlcr_model, OCI)


class TestModelFileDiscovery:
    """Test the model file discovery functionality"""
    
    def test_find_model_file_with_label_success(self):
        """Test finding model file using container label"""
        mock_result = Mock()
        mock_result.stdout.decode.return_value = "gemma3-270m.gguf"
        
        with patch('ramalama.model_store.stores.rlcr.run_cmd', return_value=mock_result) as mock_run:
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
        
        mock_result_ls = Mock()
        mock_result_ls.stdout.decode.return_value = "model1.gguf\nmodel2.txt\nmodel3.gguf"
        
        with patch('ramalama.model_store.stores.rlcr.run_cmd', side_effect=[mock_result_label, mock_result_ls]) as mock_run:
            result = find_model_file_in_image("podman", "rlcr.io/ramalama/test-model")
            
            assert result == "model1.gguf"
            assert mock_run.call_count == 2
            
            # Check the fallback ls command was called
            mock_run.assert_has_calls([
                call([
                    "podman",
                    "image", 
                    "inspect",
                    "--format={{index .Config.Labels \"com.ramalama.model.file.location\"}}",
                    "rlcr.io/ramalama/test-model",
                ]),
                call(["podman", "run", "--rm", "rlcr.io/ramalama/test-model", "ls", "/models"])
            ])
    
    def test_find_model_file_label_fails_fallback_success(self):
        """Test fallback to filesystem inspection when label inspection fails"""
        mock_result_ls = Mock()
        mock_result_ls.stdout.decode.return_value = "config.json\nmodel.gguf\nreadme.txt"
        
        with patch('ramalama.model_store.stores.rlcr.run_cmd', side_effect=[
            subprocess.CalledProcessError(1, "inspect"),
            mock_result_ls
        ]) as mock_run:
            result = find_model_file_in_image("docker", "rlcr.io/ramalama/test-model")
            
            assert result == "model.gguf"
            assert mock_run.call_count == 2
    
    def test_find_model_file_no_gguf_files(self):
        """Test when no .gguf files are found"""
        mock_result_ls = Mock()
        mock_result_ls.stdout.decode.return_value = "config.json\nreadme.txt\nmodel.bin"
        
        with patch('ramalama.model_store.stores.rlcr.run_cmd', side_effect=[
            subprocess.CalledProcessError(1, "inspect"),
            mock_result_ls
        ]) as mock_run:
            result = find_model_file_in_image("podman", "rlcr.io/ramalama/test-model")
            
            assert result is None
    
    def test_find_model_file_all_commands_fail(self):
        """Test when both label inspection and filesystem listing fail"""
        with patch('ramalama.model_store.stores.rlcr.run_cmd', side_effect=subprocess.CalledProcessError(1, "cmd")) as mock_run:
            result = find_model_file_in_image("podman", "rlcr.io/ramalama/test-model")
            
            assert result is None
            assert mock_run.call_count == 2


class TestPodmanMounting:
    """Test Podman-specific mounting logic"""
    
    @patch('ramalama.model_store.stores.rlcr.find_model_file_in_image')
    def test_setup_mounts_podman_with_model_file(self, mock_find_file, rlcr_model, args):
        """Test Podman mounting when model file is found"""
        mock_find_file.return_value = "gemma3-270m.gguf"
        rlcr_model.engine = MockEngine(use_podman=True)
        
        rlcr_model._setup_mounts_podman()
        
        expected_commands = [
            f"--mount=type=image,src=rlcr.io/ramalama/gemma3-270m,destination={MNT_DIR},subpath=/models,rw=false",
            "--init-command",
            f"ln -sf gemma3-270m.gguf {MNT_DIR}/model.file",
        ]
        
        assert rlcr_model.engine.commands == expected_commands
        mock_find_file.assert_called_once_with("podman", "rlcr.io/ramalama/gemma3-270m")
    
    @patch('ramalama.model_store.stores.rlcr.find_model_file_in_image')
    def test_setup_mounts_podman_no_model_file(self, mock_find_file, rlcr_model, args):
        """Test Podman mounting when no model file is found (fallback)"""
        mock_find_file.return_value = None
        rlcr_model.engine = MockEngine(use_podman=True)
        
        rlcr_model._setup_mounts_podman()
        
        expected_commands = [
            f"--mount=type=image,src=rlcr.io/ramalama/gemma3-270m,destination={MNT_DIR},subpath=/models,rw=false"
        ]
        
        assert rlcr_model.engine.commands == expected_commands


class TestDockerMounting:
    """Test Docker-specific mounting logic with volumes-from pattern"""
    
    @patch('ramalama.model_store.stores.rlcr.find_model_file_in_image')
    @patch('ramalama.model_store.stores.rlcr.run_cmd')
    @patch('tempfile.TemporaryDirectory')
    def test_setup_mounts_docker_success(self, mock_tempdir, mock_run_cmd, mock_find_file, rlcr_model_docker, args):
        """Test Docker mounting with successful file extraction"""
        # Note: This model should have model_name="gemma3-270m" and model_tag="latest" based on "gemma3-270m" input
        mock_find_file.return_value = "gemma3-270m.gguf"
        rlcr_model_docker.engine = MockEngine(use_podman=False)
        
        # Mock tempfile context manager
        mock_temp_ctx = MagicMock()
        mock_temp_ctx.__enter__.return_value = "/tmp/test"
        mock_temp_ctx.__exit__.return_value = None
        mock_tempdir.return_value = mock_temp_ctx
        
        rlcr_model_docker._setup_mounts_docker()
        
        # Verify that run_cmd was called multiple times for Docker setup
        assert mock_run_cmd.call_count >= 6  # At least 6 operations: rm, create, create, mkdir, cp, busybox copy, cleanup
        
        # Check that specific key commands were called
        calls = mock_run_cmd.call_args_list
        call_strings = [str(call) for call in calls]
        
        # Check data container operations (using actual model_name that will be extracted from model path)
        assert any("create" in call_str and "busybox" in call_str for call_str in call_strings)
        
        # Check docker cp command  
        assert any("cp" in call_str for call_str in call_strings)
        
        # Check that busybox was used for file operations
        assert any("busybox" in call_str for call_str in call_strings)
        
        # Verify volumes-from pattern was used - should contain the data container name
        volumes_from_cmd = None
        for cmd in rlcr_model_docker.engine.commands:
            if "--volumes-from=" in cmd:
                volumes_from_cmd = cmd
                break
        
        assert volumes_from_cmd is not None, "volumes-from command should be added to engine"
        assert "ramalama-data-" in volumes_from_cmd
    
    @patch('ramalama.model_store.stores.rlcr.find_model_file_in_image')
    @patch('ramalama.model_store.stores.rlcr.run_cmd')
    @patch('tempfile.TemporaryDirectory')
    def test_setup_mounts_docker_cleanup_on_failure(self, mock_tempdir, mock_run_cmd, mock_find_file, rlcr_model_docker):
        """Test Docker mounting ensures cleanup even when operations fail"""
        mock_find_file.return_value = "model.gguf"
        rlcr_model_docker.engine = MockEngine(use_podman=False)
        
        # Mock tempfile context manager
        mock_temp_ctx = MagicMock()
        mock_temp_ctx.__enter__.return_value = "/tmp/test"
        mock_temp_ctx.__exit__.return_value = None
        mock_tempdir.return_value = mock_temp_ctx
        
        # Make the copy operation fail to test cleanup
        def side_effect(cmd, **kwargs):
            # Fail on docker cp commands
            if len(cmd) >= 3 and cmd[1] == "cp" and "temp-" in cmd[2]:
                raise subprocess.CalledProcessError(1, cmd)
            return Mock()
        
        mock_run_cmd.side_effect = side_effect
        
        with pytest.raises(subprocess.CalledProcessError):
            rlcr_model_docker._setup_mounts_docker()
        
        # Verify cleanup was attempted - check for temp container removal
        calls = mock_run_cmd.call_args_list
        cleanup_found = any("rm" in str(call) and "temp-" in str(call) for call in calls)
        assert cleanup_found, f"Cleanup call not found in {[str(call) for call in calls]}"


class TestSetupMounts:
    """Test the main setup_mounts method that routes to engine-specific logic"""
    
    def test_setup_mounts_dryrun(self, rlcr_model, args):
        """Test that setup_mounts returns early on dryrun"""
        args.dryrun = True
        result = rlcr_model.setup_mounts(args)
        assert result is None
    
    @patch.object(RamalamaContainerRegistry, '_setup_mounts_podman')
    def test_setup_mounts_podman_engine(self, mock_podman_setup, rlcr_model, args):
        """Test routing to Podman mounting logic"""
        args.dryrun = False
        mock_engine = MockEngine(use_podman=True)
        rlcr_model.engine = mock_engine
        
        rlcr_model.setup_mounts(args)
        
        mock_podman_setup.assert_called_once()
    
    @patch.object(RamalamaContainerRegistry, '_setup_mounts_docker')
    def test_setup_mounts_docker_engine(self, mock_docker_setup, rlcr_model_docker, args):
        """Test routing to Docker mounting logic"""
        args.dryrun = False
        mock_engine = MockEngine(use_podman=False)
        rlcr_model_docker.engine = mock_engine
        
        rlcr_model_docker.setup_mounts(args)
        
        mock_docker_setup.assert_called_once()


class TestIntegration:
    """Integration tests combining multiple components"""
    
    @patch('ramalama.model_store.stores.rlcr.find_model_file_in_image')
    def test_complete_podman_flow(self, mock_find_file, rlcr_model, args):
        """Test complete flow for Podman from initialization to mount setup"""
        mock_find_file.return_value = "test-model.gguf"
        rlcr_model.engine = MockEngine(use_podman=True)
        
        # Test the complete flow
        assert rlcr_model.model == "rlcr.io/ramalama/gemma3-270m"
        assert rlcr_model._model_type == 'oci'
        
        rlcr_model.setup_mounts(args)
        
        expected_commands = [
            f"--mount=type=image,src=rlcr.io/ramalama/gemma3-270m,destination={MNT_DIR},subpath=/models,rw=false",
            "--init-command",
            f"ln -sf test-model.gguf {MNT_DIR}/model.file",
        ]
        
        assert rlcr_model.engine.commands == expected_commands
    
    def test_model_path_construction_variations(self):
        """Test various model name inputs result in correct rlcr.io paths"""
        test_cases = [
            ("simple-model", "rlcr.io/ramalama/simple-model"),
            ("model-with-tag:v1.0", "rlcr.io/ramalama/model-with-tag:v1.0"),
            ("namespace/model", "rlcr.io/ramalama/namespace/model"),
            ("complex-name_123:latest", "rlcr.io/ramalama/complex-name_123:latest"),
        ]
        
        for input_model, expected_path in test_cases:
            rlcr = RamalamaContainerRegistry(
                model=input_model,
                model_store_path="/tmp",
                conman="podman",
                ignore_stderr=False
            )
            assert rlcr.model == expected_path, f"Failed for input: {input_model}"