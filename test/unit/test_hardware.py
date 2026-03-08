"""Unit tests for hardware module."""

from unittest.mock import MagicMock, patch

import pytest

from ramalama.hardware import (
    GpuInfo,
    HardwareProfile,
    _run_cmd,
    clear_detection_cache,
    detect_cuda_version,
    detect_gpu,
    detect_hardware_profile,
    detect_rocm_version,
    get_architecture,
    get_os_type,
    is_arm,
)
from ramalama.version_constraints import Version


class TestRunCmd:
    """Tests for _run_cmd security features."""

    def test_empty_command_raises(self):
        with pytest.raises(ValueError, match="Empty command"):
            _run_cmd([])

    def test_disallowed_executable_raises(self):
        with pytest.raises(ValueError, match="Executable not in allowlist"):
            _run_cmd(["malicious-command", "--flag"])

    @patch("subprocess.run")
    def test_allowed_executable_nvidia_smi(self, mock_run):
        mock_run.return_value = MagicMock(stdout="output")
        _run_cmd(["nvidia-smi"])
        mock_run.assert_called_once()
        assert mock_run.call_args[1]["shell"] is False

    @patch("subprocess.run")
    def test_allowed_executable_rocm_smi(self, mock_run):
        mock_run.return_value = MagicMock(stdout="output")
        _run_cmd(["rocm-smi", "--showversion"])
        mock_run.assert_called_once()


class TestArchitectureDetection:
    """Tests for architecture detection."""

    @pytest.mark.parametrize(
        "machine,expected",
        [
            ("x86_64", "x86_64"),
            ("amd64", "x86_64"),
            ("arm64", "aarch64"),
            ("aarch64", "aarch64"),
            ("ARM64", "aarch64"),
            ("AARCH64", "aarch64"),
        ],
    )
    def test_get_architecture(self, machine: str, expected: str):
        with patch("platform.machine", return_value=machine):
            assert get_architecture() == expected

    @pytest.mark.parametrize(
        "machine,expected",
        [
            ("arm64", True),
            ("aarch64", True),
            ("x86_64", False),
            ("amd64", False),
            ("AARCH64", True),
            ("ARM64", True),
        ],
    )
    def test_is_arm(self, machine: str, expected: bool):
        with patch("ramalama.hardware.get_architecture") as mock_arch:
            machine_lower = machine.lower()
            if machine_lower in ("arm64", "aarch64"):
                mock_arch.return_value = "aarch64"
            else:
                mock_arch.return_value = "x86_64"
            assert is_arm() == expected


class TestOsTypeDetection:
    """Tests for OS type detection."""

    @pytest.mark.parametrize(
        "system,expected",
        [
            ("Linux", "linux"),
            ("Darwin", "darwin"),
            ("Windows", "windows"),
        ],
    )
    def test_get_os_type(self, system: str, expected: str):
        with patch("platform.system", return_value=system):
            assert get_os_type() == expected


class TestGpuInfo:
    """Tests for GpuInfo dataclass."""

    def test_default_values(self):
        gpu = GpuInfo(gpu_type="none")
        assert gpu.gpu_type == "none"
        assert gpu.driver_version is None
        assert gpu.device_count == 0
        assert gpu.memory_bytes == 0
        assert gpu.device_ids == []
        assert gpu.gfx_version == 0

    def test_with_values(self):
        version = Version(12, 4, 0)
        gpu = GpuInfo(
            gpu_type="cuda",
            driver_version=version,
            device_count=2,
            memory_bytes=8_000_000_000,
        )
        assert gpu.gpu_type == "cuda"
        assert gpu.driver_version == version
        assert gpu.device_count == 2
        assert gpu.memory_bytes == 8_000_000_000


class TestHardwareProfile:
    """Tests for HardwareProfile dataclass."""

    def test_basic_profile(self):
        gpu = GpuInfo(gpu_type="none")
        profile = HardwareProfile(
            architecture="x86_64",
            gpu=gpu,
        )
        assert profile.architecture == "x86_64"
        assert profile.gpu == gpu
        assert profile.is_container is False
        assert profile.os_type == "linux"

    def test_arm64_normalization(self):
        gpu = GpuInfo(gpu_type="none")
        profile = HardwareProfile(
            architecture="arm64",  # type: ignore
            gpu=gpu,
        )
        assert profile.architecture == "aarch64"


class TestCudaVersionDetection:
    """Tests for CUDA version detection."""

    def setup_method(self):
        clear_detection_cache()

    @patch("ramalama.hardware._run_cmd")
    def test_cuda_12_8(self, mock_run):
        mock_run.return_value = MagicMock(stdout="CUDA Version: 12.8")
        version = detect_cuda_version()
        assert version == Version(12, 8, 0)

    @patch("ramalama.hardware._run_cmd")
    def test_cuda_12_4(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="Driver Version: 550.54.14    CUDA Version: 12.4"
        )
        version = detect_cuda_version()
        assert version == Version(12, 4, 0)

    @patch("ramalama.hardware._run_cmd")
    def test_cuda_not_found(self, mock_run):
        mock_run.side_effect = OSError("nvidia-smi not found")
        version = detect_cuda_version()
        assert version is None


class TestRocmVersionDetection:
    """Tests for ROCm version detection."""

    def setup_method(self):
        clear_detection_cache()

    @patch("ramalama.hardware._run_cmd")
    def test_rocm_6_3(self, mock_run):
        mock_run.return_value = MagicMock(stdout="ROCm SMI version: 6.3.0")
        version = detect_rocm_version()
        assert version == Version(6, 3, 0)

    @patch("ramalama.hardware._run_cmd")
    def test_rocm_from_rocminfo(self, mock_run):
        def side_effect(args):
            if "rocm-smi" in args:
                raise OSError("not found")
            return MagicMock(stdout="ROCm Runtime Version: 5.7.1")

        mock_run.side_effect = side_effect
        version = detect_rocm_version()
        assert version == Version(5, 7, 1)

    @patch("ramalama.hardware._run_cmd")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_rocm_from_version_file(self, mock_read, mock_exists, mock_run):
        mock_run.side_effect = OSError("not found")
        mock_exists.return_value = True
        mock_read.return_value = "6.2.0"
        version = detect_rocm_version()
        assert version == Version(6, 2, 0)

    @patch("ramalama.hardware._run_cmd")
    @patch("pathlib.Path.exists")
    def test_rocm_not_found(self, mock_exists, mock_run):
        mock_run.side_effect = OSError("not found")
        mock_exists.return_value = False
        version = detect_rocm_version()
        assert version is None


class TestGpuDetection:
    """Tests for unified GPU detection."""

    def setup_method(self):
        clear_detection_cache()

    @patch("ramalama.hardware._detect_nvidia")
    @patch("ramalama.hardware._detect_asahi")
    def test_nvidia_gpu(self, mock_asahi, mock_nvidia):
        mock_asahi.return_value = None
        mock_nvidia.return_value = GpuInfo(
            gpu_type="cuda",
            driver_version=Version(12, 8, 0),
            device_count=1,
        )
        gpu = detect_gpu()
        assert gpu.gpu_type == "cuda"
        assert gpu.driver_version == Version(12, 8, 0)

    @patch("ramalama.hardware._detect_nvidia")
    @patch("ramalama.hardware._detect_asahi")
    @patch("ramalama.hardware._detect_ascend")
    @patch("ramalama.hardware._detect_amd")
    @patch("ramalama.hardware._detect_intel")
    @patch("ramalama.hardware._detect_mthreads")
    @patch("ramalama.hardware._detect_metal")
    def test_no_gpu_fallback(
        self, mock_metal, mock_mthreads, mock_intel, mock_amd, mock_ascend, mock_nvidia, mock_asahi
    ):
        # All detectors return None
        mock_asahi.return_value = None
        mock_nvidia.return_value = None
        mock_ascend.return_value = None
        mock_amd.return_value = None
        mock_intel.return_value = None
        mock_mthreads.return_value = None
        mock_metal.return_value = None

        gpu = detect_gpu()
        assert gpu.gpu_type == "none"


class TestHardwareProfileDetection:
    """Tests for full hardware profile detection."""

    def setup_method(self):
        clear_detection_cache()

    @patch("ramalama.hardware.detect_gpu")
    @patch("ramalama.hardware.get_architecture")
    @patch("ramalama.hardware.get_os_type")
    def test_detect_profile(self, mock_os, mock_arch, mock_gpu):
        mock_arch.return_value = "x86_64"
        mock_os.return_value = "linux"
        mock_gpu.return_value = GpuInfo(gpu_type="cuda", driver_version=Version(12, 8, 0))

        profile = detect_hardware_profile(is_container=True)

        assert profile.architecture == "x86_64"
        assert profile.os_type == "linux"
        assert profile.gpu.gpu_type == "cuda"
        assert profile.is_container is True
