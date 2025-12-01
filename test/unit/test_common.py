import os
import shutil
import subprocess
import tempfile
from contextlib import ExitStack
from pathlib import Path
from sys import platform
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

from ramalama.cli import configure_subcommands, create_argument_parser
from ramalama.common import (
    accel_image,
    check_nvidia,
    find_in_cdi,
    get_accel,
    load_cdi_config,
    populate_volume_from_image,
    rm_until_substring,
    verify_checksum,
)
from ramalama.config import DEFAULT_IMAGE, default_config


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
    input_file_name: str, content: str, expected_error: type[Exception] | None, expected_result: bool
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


DEFAULT_IMAGES = {
    "HIP_VISIBLE_DEVICES": "quay.io/ramalama/rocm",
}


@pytest.mark.parametrize(
    "accel_env,env_override,config_override,expected_result",
    [
        (None, None, None, f"{DEFAULT_IMAGE}:latest"),
        (None, f"{DEFAULT_IMAGE}:latest", None, f"{DEFAULT_IMAGE}:latest"),
        (None, None, f"{DEFAULT_IMAGE}:latest", f"{DEFAULT_IMAGE}:latest"),
        (None, f"{DEFAULT_IMAGE}:tag", None, f"{DEFAULT_IMAGE}:tag"),
        (None, None, f"{DEFAULT_IMAGE}:tag", f"{DEFAULT_IMAGE}:tag"),
        (None, f"{DEFAULT_IMAGE}@sha256:digest", None, f"{DEFAULT_IMAGE}@sha256:digest"),
        (None, None, f"{DEFAULT_IMAGE}@sha256:digest", f"{DEFAULT_IMAGE}@sha256:digest"),
        ("HIP_VISIBLE_DEVICES", None, None, "quay.io/ramalama/rocm:latest"),
        ("HIP_VISIBLE_DEVICES", f"{DEFAULT_IMAGE}:latest", None, f"{DEFAULT_IMAGE}:latest"),
        ("HIP_VISIBLE_DEVICES", None, f"{DEFAULT_IMAGE}:latest", f"{DEFAULT_IMAGE}:latest"),
    ],
)
def test_accel_image(accel_env: str, env_override, config_override: str, expected_result: str, monkeypatch):
    monkeypatch.setattr("ramalama.common.get_accel", lambda: "none")
    monkeypatch.setattr("ramalama.common.attempt_to_use_versioned", lambda *args, **kwargs: False)

    with tempfile.NamedTemporaryFile('w', delete_on_close=False) as f:
        cmdline = []
        cmdline.extend(["run", "granite"])

        env = {}
        if config_override:
            f.write(
                f"""\
[ramalama]
image = "{config_override}"
                """
            )
            f.flush()
            env["RAMALAMA_CONFIG"] = f.name
        else:
            env["RAMALAMA_CONFIG"] = "/dev/null"

        if accel_env:
            env[accel_env] = "1"
        if env_override:
            env["RAMALAMA_IMAGE"] = env_override

        with patch.dict("os.environ", env, clear=True):
            config = default_config()
            with patch("ramalama.cli.CONFIG", config):
                parser = create_argument_parser("test_accel_image")
                configure_subcommands(parser)
                assert accel_image(config) == expected_result


@patch("ramalama.config.CONFIG")
@patch("ramalama.common.run_cmd")
@patch("ramalama.common.handle_provider")
def test_apple_vm_returns_result(mock_handle_provider, mock_run_cmd, mock_config):
    mock_run_cmd.return_value.stdout = b'[{"Name": "myvm"}]'
    mock_handle_provider.return_value = True
    mock_config.user.no_missing_gpu_prompt = True
    from ramalama.common import apple_vm

    result = apple_vm("podman", mock_config)

    assert result is True
    mock_run_cmd.assert_called_once_with(
        ["podman", "machine", "list", "--format", "json", "--all-providers"], ignore_stderr=True, encoding="utf-8"
    )
    mock_handle_provider.assert_called_once_with({"Name": "myvm"}, mock_config)


class TestCheckNvidia:
    def setup_method(self):
        check_nvidia.cache_clear()

    @patch("ramalama.common.find_in_cdi")
    @patch("ramalama.common.run_cmd")
    def test_check_nvidia_smi_success(self, mock_run_cmd, mock_find_in_cdi):
        mock_find_in_cdi.return_value = (["all"], [])
        mock_run_cmd.return_value.stdout = "0,GPU-08b3c2e8-cb7b-ea3f-7711-a042c580b3e8"
        assert check_nvidia() == "cuda"

    @patch("ramalama.common.run_cmd")
    def test_check_nvidia_smi_failure(self, mock_run_cmd):
        mock_run_cmd.side_effect = subprocess.CalledProcessError(1, "nvidia-smi")
        assert check_nvidia() is None

    @patch("ramalama.common.run_cmd")
    def test_check_nvidia_smi_not_found(self, mock_run_cmd):
        mock_run_cmd.side_effect = OSError("nvidia-smi not found")
        assert check_nvidia() is None


class TestGetAccel:
    accels = [
        ("check_rocm_amd", "hip"),
        ("check_nvidia", "cuda"),
        ("check_mthreads", "musa"),
        ("check_intel", "intel"),
        ("check_ascend", "cann"),
        ("check_asahi", "asahi"),
    ]

    @pytest.mark.parametrize("accel,expected", accels)
    def test_get_accel(self, accel, expected):  # sourcery skip: no-loop-in-tests
        with ExitStack() as stack:
            for other_accel, _ in self.accels:
                return_value = expected if other_accel == accel else None
                stack.enter_context(patch(f"ramalama.common.{other_accel}", return_value=return_value))
            returned_accel = get_accel()
            assert returned_accel == expected

    def test_default_get_accel(self):  # sourcery skip: no-loop-in-tests
        with ExitStack() as stack:
            for other_accel, _ in self.accels:
                stack.enter_context(patch(f"ramalama.common.{other_accel}", return_value=None))
            returned_accel = get_accel()
            assert returned_accel == "none"


CDI_GPU_UUID = "GPU-08b3c2e8-cb7b-ea3f-7711-a042c580b3e8"

# Sample from WSL2
CDI_YAML_1 = '''
---
cdiVersion: 0.3.0
containerEdits:
  env:
  - NVIDIA_VISIBLE_DEVICES=void
  hooks:
  - args:
    - nvidia-cdi-hook
    - create-symlinks
    - --link
    - /usr/lib/wsl/drivers/nvlti.inf_amd64_4bd2a3580753f54d/nvidia-smi::/usr/bin/nvidia-smi
    hookName: createContainer
    path: /usr/bin/nvidia-cdi-hook
devices:
- containerEdits:
    deviceNodes:
    - path: /dev/dxg
  name: all
kind: nvidia.com/gpu
'''

CDI_YAML_2 = '''
---
cdiVersion: 0.5.0
containerEdits:
  deviceNodes:
  - path: /dev/nvidia-modeset
  - path: /dev/nvidia-uvm
  - path: /dev/nvidia-uvm-tools
  - path: /dev/nvidiactl
  env:
  - NVIDIA_VISIBLE_DEVICES=void
  hooks:
  - args:
    - nvidia-cdi-hook
    - create-symlinks
    - --link
    - ../libnvidia-allocator.so.1::/usr/lib64/gbm/nvidia-drm_gbm.so
    env:
    - NVIDIA_CTK_DEBUG=false
    hookName: createContainer
    path: /usr/bin/nvidia-cdi-hook
devices:
- containerEdits:
    deviceNodes:
    - path: /dev/nvidia0
    - path: /dev/dri/card1
    - path: /dev/dri/renderD128
    hooks:
    - args:
      - nvidia-cdi-hook
      - create-symlinks
      - --link
      - ../card1::/dev/dri/by-path/pci-0000:52:00.0-card
      - --link
      - ../renderD128::/dev/dri/by-path/pci-0000:52:00.0-render
      env:
      - NVIDIA_CTK_DEBUG=false
      hookName: createContainer
      path: /usr/bin/nvidia-cdi-hook
  name: "0"
- containerEdits:
    deviceNodes:
    - path: /dev/nvidia0
    - path: /dev/dri/card1
    - path: /dev/dri/renderD128
    hooks:
    - args:
      - nvidia-cdi-hook
      - create-symlinks
      - --link
      - ../card1::/dev/dri/by-path/pci-0000:52:00.0-card
      - --link
      - ../renderD128::/dev/dri/by-path/pci-0000:52:00.0-render
      env:
      - NVIDIA_CTK_DEBUG=false
      hookName: createContainer
      path: /usr/bin/nvidia-cdi-hook
  name: GPU-08b3c2e8-cb7b-ea3f-7711-a042c580b3e8
- containerEdits:
    deviceNodes:
    - path: /dev/nvidia0
    - path: /dev/dri/card1
    - path: /dev/dri/renderD128
    hooks:
    - args:
      - nvidia-cdi-hook
      - create-symlinks
      - --link
      - ../card1::/dev/dri/by-path/pci-0000:52:00.0-card
      - --link
      - ../renderD128::/dev/dri/by-path/pci-0000:52:00.0-render
      env:
      - NVIDIA_CTK_DEBUG=false
      hookName: createContainer
      path: /usr/bin/nvidia-cdi-hook
  name: all
kind: nvidia.com/gpu
'''

CDI_JSON_1 = '''
{"cdiVersion":"0.3.0","kind":"nvidia.com/gpu","devices":[{"name":"all","containerEdits":{"deviceNodes":[{"path":"/dev/dxg"}]}}],"containerEdits":{"env":["NVIDIA_VISIBLE_DEVICES=void"]}}
'''
CDI_JSON_2 = '''
{"cdiVersion":"0.5.0","kind":"nvidia.com/gpu","devices":[{"name":"0","containerEdits":{"deviceNodes":[{"path":"/dev/nvidia0"},{"path":"/dev/dri/card1"},{"path":"/dev/dri/renderD128"}],"hooks":[{"hookName":"createContainer","path":"/usr/bin/nvidia-cdi-hook","args":["nvidia-cdi-hook","create-symlinks","--link","../card1::/dev/dri/by-path/pci-0000:52:00.0-card","--link","../renderD128::/dev/dri/by-path/pci-0000:52:00.0-render"]},{"hookName":"createContainer","path":"/usr/bin/nvidia-cdi-hook","args":["nvidia-cdi-hook","chmod","--mode","755","--path","/dev/dri"]}]}},{"name":"GPU-08b3c2e8-cb7b-ea3f-7711-a042c580b3e8","containerEdits":{"deviceNodes":[{"path":"/dev/nvidia0"},{"path":"/dev/dri/card1"},{"path":"/dev/dri/renderD128"}],"hooks":[{"hookName":"createContainer","path":"/usr/bin/nvidia-cdi-hook","args":["nvidia-cdi-hook","create-symlinks","--link","../card1::/dev/dri/by-path/pci-0000:52:00.0-card","--link","../renderD128::/dev/dri/by-path/pci-0000:52:00.0-render"]},{"hookName":"createContainer","path":"/usr/bin/nvidia-cdi-hook","args":["nvidia-cdi-hook","chmod","--mode","755","--path","/dev/dri"]}]}},{"name":"all","containerEdits":{"deviceNodes":[{"path":"/dev/nvidia0"},{"path":"/dev/dri/card1"},{"path":"/dev/dri/renderD128"}],"hooks":[{"hookName":"createContainer","path":"/usr/bin/nvidia-cdi-hook","args":["nvidia-cdi-hook","create-symlinks","--link","../card1::/dev/dri/by-path/pci-0000:52:00.0-card","--link","../renderD128::/dev/dri/by-path/pci-0000:52:00.0-render"]},{"hookName":"createContainer","path":"/usr/bin/nvidia-cdi-hook","args":["nvidia-cdi-hook","chmod","--mode","755","--path","/dev/dri"]}]}}],"containerEdits":{"env":["NVIDIA_VISIBLE_DEVICES=void"]}}'''  # noqa: E501


@pytest.mark.parametrize(
    "filename,source,expected",
    [
        pytest.param(
            "nvidia.yaml",
            CDI_YAML_1,
            [
                "all",
            ],
            id="YAML-all",
        ),
        pytest.param("nvidia.yaml", CDI_YAML_2, ["0", "all", CDI_GPU_UUID], id="YAML-0-UUID-all"),
        pytest.param(
            "nvidia.json",
            CDI_JSON_1,
            [
                "all",
            ],
            id="JSON-all",
        ),
        pytest.param(
            "nvidia.json",
            CDI_JSON_2,
            [
                "0",
                CDI_GPU_UUID,
                "all",
            ],
            id="JSON-0-UUID-all",
        ),
    ],
)
def test_load_cdi_config(filename, source, expected):
    with patch("os.walk", return_value=(("/etc/cdi", None, (filename,)),)):
        with patch("builtins.open", mock_open(read_data=source)):
            cdi = load_cdi_config(["/var/run/cdi", "/etc/cdi"])
            assert cdi
            assert "devices" in cdi
            devices = cdi["devices"]
            names = [device["name"] for device in devices]
            assert set(expected) == set(names)


@pytest.mark.parametrize(
    "visible,conf,unconf",
    [
        (["all"], ["all"], []),
        (["0", "all"], ["0", "all"], []),
        ([CDI_GPU_UUID, "all"], [CDI_GPU_UUID, "all"], []),
        (["1", "all"], ["all"], ["1"]),
        (["dummy", "all"], ["all"], ["dummy"]),
    ],
)
@patch("builtins.open", mock_open(read_data=CDI_YAML_2))
@patch("os.walk", return_value=(("/etc/cdi", None, ("nvidia.yaml",)),))
def test_find_in_cdi(mock_walk, visible, conf, unconf):
    assert find_in_cdi(visible) == (conf, unconf)


@pytest.mark.parametrize(
    "visible,conf,unconf",
    [
        (["all"], [], ["all"]),
        (["0", "all"], [], ["0", "all"]),
        ([CDI_GPU_UUID, "all"], [], [CDI_GPU_UUID, "all"]),
    ],
)
@patch("builtins.open", mock_open(read_data="asdf\n- ghjk\n"))
@patch("os.walk", return_value=(("/etc/cdi", None, ("nvidia.yaml",)),))
def test_find_in_cdi_broken(mock_walk, visible, conf, unconf):
    assert find_in_cdi(visible) == (conf, unconf)


@patch("ramalama.common.load_cdi_config", return_value=None)
def test_find_in_cdi_no_config(mock_load_cdi_config):
    assert find_in_cdi(["all"]) == ([], ["all"])


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
