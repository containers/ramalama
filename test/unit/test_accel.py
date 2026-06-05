import os
from contextlib import ExitStack
from unittest.mock import mock_open, patch

import pytest

from ramalama.accel import (
    accel_image,
    check_intel,
    check_nvidia,
    find_in_cdi,
    get_accel,
    load_cdi_config,
)
from ramalama.cli import (
    default_image,
    default_rag_image,
    default_tools_image,
    parse_args_from_cmd,
)
from ramalama.compat import NamedTemporaryFile
from ramalama.config import DEFAULT_IMAGE, load_config
from ramalama.hw_detect import DeviceInfo, clear_all_detection_caches

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
    monkeypatch.setattr("ramalama.accel.get_accel", lambda: "none")

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
                default_tools_image.cache_clear()
                parse_args_from_cmd(cmdline)
                assert accel_image(config) == expected_result


class TestCheckNvidia:
    def setup_method(self):
        check_nvidia.cache_clear()
        clear_all_detection_caches()

    @patch("ramalama.accel.find_in_cdi")
    @patch("ramalama.hw_detect.detect_nvidia")
    def test_check_nvidia_success(self, mock_detect, mock_find_in_cdi):
        mock_find_in_cdi.return_value = (["all"], [])
        mock_detect.return_value = [
            DeviceInfo("RTX 4090", 24564 * 1024 * 1024, index=0, uuid="GPU-08b3c2e8-cb7b-ea3f-7711-a042c580b3e8"),
        ]
        assert check_nvidia() == "cuda"

    @patch("ramalama.hw_detect.detect_nvidia")
    def test_check_nvidia_no_gpus(self, mock_detect):
        mock_detect.return_value = []
        assert check_nvidia() is None


class TestCheckIntel:
    def setup_method(self):
        clear_all_detection_caches()

    @patch("ramalama.hw_detect.detect_intel")
    def test_check_intel_sets_env(self, mock_detect):
        mock_detect.return_value = [DeviceInfo("Intel Arc B580", 12 * 1024**3)]
        with patch.dict("os.environ", {}, clear=True):
            result = check_intel()
            assert result == "intel"
            assert os.environ["INTEL_VISIBLE_DEVICES"] == "1"

    @patch("ramalama.hw_detect.detect_intel")
    def test_check_intel_no_gpus(self, mock_detect):
        mock_detect.return_value = []
        result = check_intel()
        assert result is None

    @patch("ramalama.hw_detect.detect_intel")
    def test_check_intel_multiple_gpus(self, mock_detect):
        mock_detect.return_value = [
            DeviceInfo("Intel Arc B580", 12 * 1024**3),
            DeviceInfo("Intel Arc A770", 16 * 1024**3),
        ]
        with patch.dict("os.environ", {}, clear=True):
            result = check_intel()
            assert result == "intel"
            assert os.environ["INTEL_VISIBLE_DEVICES"] == "2"


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
        check_nvidia.cache_clear()
        clear_all_detection_caches()

    @pytest.mark.parametrize("accel,expected", accels)
    def test_get_accel(self, accel, expected):  # sourcery skip: no-loop-in-tests
        with ExitStack() as stack:
            for other_accel, _ in self.accels:
                return_value = expected if other_accel == accel else None
                stack.enter_context(patch(f"ramalama.accel.{other_accel}", return_value=return_value))
            returned_accel = get_accel()
            assert returned_accel == expected

    def test_default_get_accel(self):  # sourcery skip: no-loop-in-tests
        with ExitStack() as stack:
            for other_accel, _ in self.accels:
                stack.enter_context(patch(f"ramalama.accel.{other_accel}", return_value=None))
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


@patch("ramalama.accel.load_cdi_config", return_value=None)
def test_find_in_cdi_no_config(mock_load_cdi_config):
    assert find_in_cdi(["all"]) == ([], ["all"])
