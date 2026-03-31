import os
import shutil
import subprocess
from contextlib import ExitStack
from pathlib import Path
from sys import platform
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

from ramalama.cli import (
    default_image,
    default_rag_image,
    parse_args_from_cmd,
)
from ramalama.common import (
    accel_image,
    check_nvidia,
    ensure_image,
    find_in_cdi,
    get_accel,
    load_cdi_config,
    populate_volume_from_image,
    rm_until_substring,
    verify_checksum,
)
from ramalama.compat import NamedTemporaryFile
from ramalama.config import DEFAULT_IMAGE, load_config


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


_BASE_IMAGE = "quay.io/ramalama/ramalama"

DEFAULT_IMAGES = {
    "HIP_VISIBLE_DEVICES": "quay.io/ramalama/rocm",
}


@pytest.mark.parametrize(
    "accel_env,env_override,config_override,cli_override,expected_result",
    [
        (None, None, None, None, DEFAULT_IMAGE),
        (None, f"{_BASE_IMAGE}:latest", None, None, f"{_BASE_IMAGE}:latest"),
        (None, None, f"{_BASE_IMAGE}:latest", None, f"{_BASE_IMAGE}:latest"),
        (None, f"{_BASE_IMAGE}:tag", None, None, f"{_BASE_IMAGE}:tag"),
        (None, None, f"{_BASE_IMAGE}:tag", None, f"{_BASE_IMAGE}:tag"),
        (None, None, None, f"{_BASE_IMAGE}:tag", f"{_BASE_IMAGE}:tag"),
        (None, f"{_BASE_IMAGE}@sha256:digest", None, None, f"{_BASE_IMAGE}@sha256:digest"),
        (None, None, f"{_BASE_IMAGE}@sha256:digest", None, f"{_BASE_IMAGE}@sha256:digest"),
        (None, None, None, f"{_BASE_IMAGE}@sha256:digest", f"{_BASE_IMAGE}@sha256:digest"),
        # AMD GPU defaults to Vulkan (ramalama image, version-tagged)
        ("HIP_VISIBLE_DEVICES", None, None, None, DEFAULT_IMAGE),
        ("HIP_VISIBLE_DEVICES", f"{_BASE_IMAGE}:latest", None, None, f"{_BASE_IMAGE}:latest"),
        ("HIP_VISIBLE_DEVICES", None, f"{_BASE_IMAGE}:latest", None, f"{_BASE_IMAGE}:latest"),
        ("HIP_VISIBLE_DEVICES", None, None, f"{_BASE_IMAGE}:latest", f"{_BASE_IMAGE}:latest"),
    ],
)
def test_accel_image(
    accel_env: str, env_override, config_override: str, cli_override: str, expected_result: str, monkeypatch
):
    monkeypatch.setattr("ramalama.common.get_accel", lambda: "none")

    with NamedTemporaryFile('w', delete_on_close=False) as f:
        cmdline = ["run"]
        if cli_override:
            cmdline.extend(["--image", cli_override])
        cmdline.append("granite")

        env = {}
        if config_override:
            f.write(f"""\
[ramalama]
image = "{config_override}"
                """)
            f.flush()
            env["RAMALAMA_CONFIG"] = f.name
        else:
            env["RAMALAMA_CONFIG"] = "/dev/null"

        if accel_env:
            env[accel_env] = "1"
        if env_override:
            env["RAMALAMA_IMAGE"] = env_override

        with patch.dict("os.environ", env, clear=True):
            config = load_config()
            with patch("ramalama.cli.ActiveConfig", return_value=config):
                default_image.cache_clear()
                default_rag_image.cache_clear()
                parse_args_from_cmd(cmdline)
                assert accel_image(config) == expected_result


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

    def setup_method(self):
        get_accel.cache_clear()

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
    with patch("os.path.isdir", return_value=True):
        with patch("os.walk", return_value=(("/etc/cdi", None, (filename,)),)):
            with patch("builtins.open", mock_open(read_data=source)):
                cdi = load_cdi_config(["/var/run/cdi", "/etc/cdi"])
                assert cdi
                assert "devices" in cdi
                devices = cdi["devices"]
                names = [device["name"] for device in devices]
                assert set(expected) == set(names)


def test_load_cdi_config_merges_multiple_files():
    """When multiple CDI files exist, devices are merged and deduped by name (fixes #2485)."""
    # Simulate /var/run/cdi with a k8s file and /etc/cdi with an nvidia file.
    # Device "0" appears in both files to verify deduplication (first-seen is kept).
    k8s_spec = '{"kind":"k8s.device-plugin.nvidia.com/gpu","devices":[{"name":"GPU-abc123"},{"name":"0","annotations":{"source":"k8s"}}]}'  # noqa: E501
    nvidia_spec = '{"kind":"nvidia.com/gpu","devices":[{"name":"all"},{"name":"0","annotations":{"source":"nvidia"}}]}'

    def walk_side_effect(spec_dir):
        if spec_dir == "/var/run/cdi":
            yield ("/var/run/cdi", None, ("k8s.device-plugin.nvidia.com-gpu.json",))
        if spec_dir == "/etc/cdi":
            yield ("/etc/cdi", None, ("nvidia.yaml",))

    def open_side_effect(path, *args, **kwargs):
        path_str = str(path)
        if "k8s.device-plugin" in path_str:
            return mock_open(read_data=k8s_spec)(path, *args, **kwargs)
        if "nvidia" in path_str:
            return mock_open(read_data=nvidia_spec)(path, *args, **kwargs)
        return mock_open(read_data="")(path, *args, **kwargs)

    with patch("os.path.isdir", return_value=True):
        with patch("os.walk", side_effect=walk_side_effect):
            with patch("builtins.open", side_effect=open_side_effect):
                cdi = load_cdi_config(["/var/run/cdi", "/etc/cdi"])
    assert cdi is not None
    devices = cdi["devices"]
    names = [d["name"] for d in devices]
    # Merged: GPU-abc123 and "0" from k8s file, "all" from nvidia file (second "0" deduped)
    assert set(names) == {"GPU-abc123", "all", "0"}
    assert names.count("0") == 1
    # First-seen device "0" (from k8s) is kept
    device_0 = next(d for d in devices if d["name"] == "0")
    assert device_0.get("annotations", {}).get("source") == "k8s"


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
@patch("os.path.isdir", return_value=True)
@patch("builtins.open", mock_open(read_data=CDI_YAML_2))
@patch("os.walk", return_value=(("/etc/cdi", None, ("nvidia.yaml",)),))
def test_find_in_cdi(mock_isdir, mock_walk, visible, conf, unconf):
    assert find_in_cdi(visible) == (conf, unconf)


@pytest.mark.parametrize(
    "visible,conf,unconf",
    [
        (["all"], [], ["all"]),
        (["0", "all"], [], ["0", "all"]),
        ([CDI_GPU_UUID, "all"], [], [CDI_GPU_UUID, "all"]),
    ],
)
@patch("os.path.isdir", return_value=True)
@patch("builtins.open", mock_open(read_data="asdf\n- ghjk\n"))
@patch("os.walk", return_value=(("/etc/cdi", None, ("nvidia.yaml",)),))
def test_find_in_cdi_broken(mock_isdir, mock_walk, visible, conf, unconf):
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
