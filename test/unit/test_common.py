import os
import shutil
import subprocess
from pathlib import Path
from sys import platform
from typing import Optional
from unittest.mock import MagicMock, Mock, patch

import pytest

from ramalama.common import (
    ensure_image,
    populate_volume_from_image,
    rm_until_substring,
    verify_checksum,
)


@pytest.mark.parametrize(
    "input,rm_until,expected",
    [
        ("", "", ""),
        ("huggingface://granite-code", "://", "granite-code"),
        ("hf://granite-code", "://", "granite-code"),
        ("hf.co/granite-code", "hf.co/", "granite-code"),
        (
            "http://huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf",
            ".co/",
            "ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf",
        ),
        ("modelscope://granite-code", "://", "granite-code"),
        ("ms://granite-code", "://", "granite-code"),
        (
            "file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf",
            "",
            "file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf",
        ),
    ],
)
def test_rm_until_substring(input: str, rm_until: str, expected: str):
    actual = rm_until_substring(input, rm_until)
    assert actual == expected


valid_input = """{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ if .Prompt }}<|im_start|>user
{{ .Prompt }}<|im_end|>
{{ end }}<|im_start|>assistant
{{ .Response }}<|im_end|>
"""

tampered_input = """{"model_format":"gguf","model_family":"llama","model_families":["llama"],"model_type":"361.82M","file_type":"Q4_0","architecture":"amd64","os":"linux","rootfs":{"type":"layers","diff_ids":["sha256:f7ae49f9d598730afa2de96fc7dade47f5850446bf813df2e9d739cc8a6c4f29","sha256:62fbfd9ed093d6e5ac83190c86eec5369317919f4b149598d2dbb38900e9faef","sha256:cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30","sha256:ca7a9654b5469dc2d638456f31a51a03367987c54135c089165752d9eeb08cd7"]}}

I have been tampered with

"""  # noqa: E501


@pytest.mark.parametrize(
    "input_file_name,content,expected_error,expected_result",
    [
        ("invalidname", "", ValueError, None),
        ("sha256:123", "RamaLama - make working with AI boring through the use of OCI containers.", ValueError, None),
        ("sha256:62fbfd9ed093d6e5ac83190c86eec5369317919f4b149598d2dbb38900e9faef", valid_input, None, True),
        ("sha256-62fbfd9ed093d6e5ac83190c86eec5369317919f4b149598d2dbb38900e9faef", valid_input, None, True),
        ("sha256:16cd1aa2bd52b0e87ff143e8a8a7bb6fcb0163c624396ca58e7f75ec99ef081f", tampered_input, None, False),
    ],
)
def test_verify_checksum(
    input_file_name: str, content: str, expected_error: Optional[type[Exception]], expected_result: bool
):
    # skip this test case on Windows since colon is not a valid file symbol
    if ":" in input_file_name and platform == "win32":
        return

    full_dir_path = os.path.join(Path(__file__).parent, "verify_checksum")
    file_path = os.path.join(full_dir_path, input_file_name)

    try:
        os.makedirs(full_dir_path, exist_ok=True)
        with open(file_path, "w") as f:
            f.write(content)

        if expected_error is None:
            assert verify_checksum(file_path) == expected_result
            return

        with pytest.raises(expected_error):
            verify_checksum(file_path)
    finally:
        shutil.rmtree(full_dir_path)


@patch("ramalama.common.run_cmd")
@patch("ramalama.common.handle_provider")
def test_apple_vm_returns_result(mock_handle_provider, mock_run_cmd):
    mock_run_cmd.return_value.stdout = b'[{"Name": "myvm"}]'
    mock_handle_provider.return_value = True
    config = object()
    from ramalama.common import apple_vm

    result = apple_vm("podman", config)

    assert result is True
    mock_run_cmd.assert_called_once_with(
        ["podman", "machine", "list", "--format", "json", "--all-providers"], ignore_stderr=True, encoding="utf-8"
    )
    mock_handle_provider.assert_called_once_with({"Name": "myvm"}, config)


@patch("ramalama.common.run_cmd", side_effect=FileNotFoundError("podman: command not found"))
def test_apple_vm_returns_false_when_podman_not_installed(mock_run_cmd):
    from ramalama.common import apple_vm

    result = apple_vm("podman", None)

    assert result is False
    mock_run_cmd.assert_called_once()


class TestEnsureImage:
    """Tests for ensure_image()"""

    def test_no_conman_returns_image_unchanged(self):
        assert ensure_image(None, "myimage:1.0") == "myimage:1.0"
        assert ensure_image("", "myimage:1.0") == "myimage:1.0"

    def test_adds_latest_tag_when_missing(self):
        with patch("ramalama.common.run_cmd", side_effect=Exception("not found")):
            result = ensure_image("podman", "myimage")
        assert result == "myimage:latest"

    @patch("ramalama.common.run_cmd")
    def test_found_locally_returns_image(self, mock_run_cmd):
        mock_run_cmd.return_value = True
        result = ensure_image("podman", "myimage:1.0")
        assert result == "myimage:1.0"
        mock_run_cmd.assert_called_once_with(["podman", "inspect", "myimage:1.0"], ignore_all=True)

    @patch("ramalama.common.run_cmd", side_effect=subprocess.CalledProcessError(125, "podman"))
    def test_not_found_locally_no_pull_returns_image(self, mock_run_cmd):
        result = ensure_image("podman", "myimage:1.0", should_pull=False)
        assert result == "myimage:1.0"

    @patch("ramalama.common.run_cmd")
    def test_pull_succeeds_returns_image(self, mock_run_cmd):
        # inspect raises (not found), pull succeeds
        mock_run_cmd.side_effect = [subprocess.CalledProcessError(125, "podman"), MagicMock()]
        result = ensure_image("podman", "myimage:1.0", should_pull=True)
        assert result == "myimage:1.0"

    @patch("ramalama.common.run_cmd")
    def test_pull_fails_non_ramalama_image_raises(self, mock_run_cmd):
        mock_run_cmd.side_effect = subprocess.CalledProcessError(125, "podman")
        with pytest.raises(ValueError, match="Failed to pull image myimage:1.0"):
            ensure_image("podman", "myimage:1.0", should_pull=True)

    @patch("ramalama.common.run_cmd")
    def test_pull_fails_ramalama_image_fallback_succeeds(self, mock_run_cmd):
        # inspect fails, versioned pull fails, :latest pull succeeds
        mock_run_cmd.side_effect = [
            subprocess.CalledProcessError(125, "podman"),  # inspect
            subprocess.CalledProcessError(125, "podman"),  # pull versioned
            MagicMock(),  # pull :latest
        ]
        result = ensure_image("podman", "quay.io/ramalama/ramalama:0.17", should_pull=True)
        assert result == "quay.io/ramalama/ramalama:latest"

    @patch("ramalama.common.run_cmd")
    def test_pull_fails_ramalama_image_fallback_fails_raises(self, mock_run_cmd):
        mock_run_cmd.side_effect = subprocess.CalledProcessError(125, "podman")
        with pytest.raises(ValueError, match="Failed to pull image quay.io/ramalama/ramalama:0.17"):
            ensure_image("podman", "quay.io/ramalama/ramalama:0.17", should_pull=True)


class TestPopulateVolumeFromImage:
    """Test the populate_volume_from_image function for Docker volume creation"""

    @pytest.fixture
    def mock_model(self):
        """Create a mock model with required attributes"""
        model = Mock()
        model.model = "test-registry.io/test-model:latest"
        model.conman = "docker"
        return model

    @patch('subprocess.Popen')
    @patch('ramalama.common.run_cmd')
    def test_populate_volume_success(self, mock_run_cmd, mock_popen, mock_model):
        """Test successful volume population with Docker"""
        output_filename = "model.gguf"

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

        result = populate_volume_from_image(mock_model, Mock(engine="docker"), output_filename)

        assert result.startswith("ramalama-models-")

        assert mock_run_cmd.call_count >= 3
        assert mock_popen.call_count == 2

    @patch('subprocess.Popen')
    @patch('ramalama.common.run_cmd')
    def test_populate_volume_export_failure(self, _, mock_popen, mock_model):
        """Test handling of export process failure"""
        output_filename = "model.gguf"

        # Mock export process failure
        mock_export_proc = MagicMock()
        mock_export_proc.stdout = Mock()
        mock_export_proc.wait.return_value = 1  # Failure
        mock_export_proc.__enter__ = Mock(return_value=mock_export_proc)
        mock_export_proc.__exit__ = Mock(return_value=None)

        mock_tar_proc = MagicMock()
        mock_tar_proc.wait.return_value = 0
        mock_tar_proc.__enter__ = Mock(return_value=mock_tar_proc)
        mock_tar_proc.__exit__ = Mock(return_value=None)

        mock_popen.side_effect = [mock_export_proc, mock_tar_proc]

        with pytest.raises(subprocess.CalledProcessError):
            populate_volume_from_image(mock_model, Mock(engine="docker"), output_filename)

    @patch('subprocess.Popen')
    @patch('ramalama.common.run_cmd')
    def test_populate_volume_tar_failure(self, _, mock_popen, mock_model):
        """Test handling of tar process failure"""
        output_filename = "model.gguf"

        # Mock tar process failure
        mock_export_proc = MagicMock()
        mock_export_proc.stdout = Mock()
        mock_export_proc.wait.return_value = 0
        mock_export_proc.__enter__ = Mock(return_value=mock_export_proc)
        mock_export_proc.__exit__ = Mock(return_value=None)

        mock_tar_proc = MagicMock()
        mock_tar_proc.wait.return_value = 1  # Failure
        mock_tar_proc.__enter__ = Mock(return_value=mock_tar_proc)
        mock_tar_proc.__exit__ = Mock(return_value=None)

        mock_popen.side_effect = [mock_export_proc, mock_tar_proc]

        with pytest.raises(subprocess.CalledProcessError):
            populate_volume_from_image(mock_model, Mock(engine="docker"), output_filename)

    def test_volume_name_generation(self, mock_model):
        """Test that volume names are generated consistently based on model hash"""
        import hashlib

        expected_hash = hashlib.sha256(mock_model.model.encode()).hexdigest()[:12]
        expected_volume = f"ramalama-models-{expected_hash}"

        with patch('subprocess.Popen') as mock_popen, patch('ramalama.common.run_cmd'):
            # Mock successful processes
            mock_proc = MagicMock()
            mock_proc.wait.return_value = 0
            mock_proc.__enter__ = Mock(return_value=mock_proc)
            mock_proc.__exit__ = Mock(return_value=None)
            mock_popen.return_value = mock_proc

            result = populate_volume_from_image(mock_model, Mock(engine="docker"), "test.gguf")
            assert result == expected_volume
