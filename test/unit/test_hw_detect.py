import builtins
import json
import subprocess
from unittest.mock import MagicMock, mock_open, patch

import pytest

from ramalama.hw_detect import (
    INTEL_GPU_SPECS,
    VK_MEMORY_HEAP_DEVICE_LOCAL_BIT,
    VK_PHYSICAL_DEVICE_TYPE_CPU,
    VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU,
    AmdRocmDetector,
    AppleSiliconDetector,
    AsahiDetector,
    AscendDetector,
    CpuDetector,
    DeviceInfo,
    IntelDetector,
    MthreadsDetector,
    NvidiaDetector,
    VulkanDetector,
    _get_system_memory,
    _VulkanDeviceRaw,
    clear_all_detection_caches,
    detect_all_hardware,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_all_detection_caches()
    yield
    clear_all_detection_caches()


class TestDetectNvidia:
    def test_single_gpu(self):
        mock_result = MagicMock()
        mock_result.stdout = "0, GPU-abc123, 24564, NVIDIA GeForce RTX 4090\n"
        with patch("ramalama.hw_detect.subprocess.run", return_value=mock_result):
            result = NvidiaDetector().detect()
        assert len(result) == 1
        assert result[0].name == "NVIDIA GeForce RTX 4090"
        assert result[0].memory_bytes == 24564 * 1024 * 1024
        assert result[0].index == 0
        assert result[0].uuid == "GPU-abc123"

    def test_multi_gpu_returns_all(self):
        mock_result = MagicMock()
        mock_result.stdout = "0, GPU-aaa, 8192, NVIDIA GeForce RTX 3070\n1, GPU-bbb, 24564, NVIDIA GeForce RTX 4090\n"
        with patch("ramalama.hw_detect.subprocess.run", return_value=mock_result):
            result = NvidiaDetector().detect()
        assert len(result) == 2
        assert result[0].name == "NVIDIA GeForce RTX 3070"
        assert result[0].memory_bytes == 8192 * 1024 * 1024
        assert result[0].index == 0
        assert result[1].name == "NVIDIA GeForce RTX 4090"
        assert result[1].memory_bytes == 24564 * 1024 * 1024
        assert result[1].index == 1

    def test_nvidia_smi_not_found(self):
        with patch("ramalama.hw_detect.subprocess.run", side_effect=OSError):
            result = NvidiaDetector().detect()
        assert result == []

    def test_nvidia_smi_fails(self):
        with patch("ramalama.hw_detect.subprocess.run", side_effect=subprocess.CalledProcessError(1, "nvidia-smi")):
            result = NvidiaDetector().detect()
        assert result == []

    def test_empty_output(self):
        mock_result = MagicMock()
        mock_result.stdout = ""
        with patch("ramalama.hw_detect.subprocess.run", return_value=mock_result):
            result = NvidiaDetector().detect()
        assert result == []

    def test_malformed_output(self):
        mock_result = MagicMock()
        mock_result.stdout = "not a valid line\n"
        with patch("ramalama.hw_detect.subprocess.run", return_value=mock_result):
            result = NvidiaDetector().detect()
        assert result == []


class TestDetectAmdRocm:
    def _make_mock_amdkfd(self, gpus_data, bank_props_map=None, bank_props=None):
        mock_module = MagicMock()
        mock_module.HEAP_TYPE_FB_PUBLIC = 1
        mock_module.HEAP_TYPE_FB_PRIVATE = 2
        mock_module.gpus.return_value = gpus_data
        if bank_props_map:
            mock_module.parse_props.side_effect = lambda path: bank_props_map.get(
                path, {"heap_type": 0, "size_in_bytes": 0}
            )
        elif bank_props:
            mock_module.parse_props.return_value = bank_props
        return mock_module

    def test_single_gpu(self):
        mock_amdkfd = self._make_mock_amdkfd(
            gpus_data=[
                ("/sys/topology/nodes/1", {"gfx_target_version": 90012, "mem_banks_count": 1, "device_id": 0x1636})
            ],
            bank_props={"heap_type": 1, "size_in_bytes": 8 * 1024**3},
        )

        with (
            patch("ramalama.hw_detect.platform.machine", return_value="x86_64"),
            patch("ramalama.hw_detect.importlib.import_module", return_value=mock_amdkfd),
            patch.object(builtins, "open", mock_open(read_data="renoir\n")),
        ):
            result = AmdRocmDetector().detect()

        assert len(result) == 1
        assert result[0].name == "AMD Renoir"
        assert result[0].memory_bytes == 8 * 1024**3

    def test_name_file_missing_falls_back_to_device_id(self):
        mock_amdkfd = self._make_mock_amdkfd(
            gpus_data=[
                ("/sys/topology/nodes/1", {"gfx_target_version": 90012, "mem_banks_count": 1, "device_id": 0x1636})
            ],
            bank_props={"heap_type": 1, "size_in_bytes": 8 * 1024**3},
        )

        with (
            patch("ramalama.hw_detect.platform.machine", return_value="x86_64"),
            patch("ramalama.hw_detect.importlib.import_module", return_value=mock_amdkfd),
            patch.object(builtins, "open", side_effect=OSError),
        ):
            result = AmdRocmDetector().detect()

        assert len(result) == 1
        assert result[0].name == "AMD GPU (0x1636)"

    def test_multi_gpu_returns_all(self):
        mock_amdkfd = self._make_mock_amdkfd(
            gpus_data=[
                ("/sys/topology/nodes/1", {"gfx_target_version": 90012, "mem_banks_count": 1, "device_id": 0x1636}),
                ("/sys/topology/nodes/2", {"gfx_target_version": 90012, "mem_banks_count": 1, "device_id": 0x1637}),
            ],
            bank_props={"heap_type": 1, "size_in_bytes": 8 * 1024**3},
        )

        name_map = {"/sys/topology/nodes/1/name": "navi31\n", "/sys/topology/nodes/2/name": "navi32\n"}

        def fake_open(path, *args, **kwargs):
            if path in name_map:
                return mock_open(read_data=name_map[path])()
            raise OSError

        with (
            patch("ramalama.hw_detect.platform.machine", return_value="x86_64"),
            patch("ramalama.hw_detect.importlib.import_module", return_value=mock_amdkfd),
            patch.object(builtins, "open", side_effect=fake_open),
        ):
            result = AmdRocmDetector().detect()

        assert len(result) == 2
        assert result[0].name == "AMD Navi31"
        assert result[1].name == "AMD Navi32"

    def test_old_gpu_skipped(self):
        mock_amdkfd = self._make_mock_amdkfd(
            gpus_data=[
                ("/sys/topology/nodes/1", {"gfx_target_version": 80000, "mem_banks_count": 1, "device_id": 0x1234})
            ],
            bank_props={"heap_type": 1, "size_in_bytes": 4 * 1024**3},
        )

        with (
            patch("ramalama.hw_detect.platform.machine", return_value="x86_64"),
            patch("ramalama.hw_detect.importlib.import_module", return_value=mock_amdkfd),
        ):
            result = AmdRocmDetector().detect()

        assert result == []

    def test_import_error(self):
        with (
            patch("ramalama.hw_detect.platform.machine", return_value="x86_64"),
            patch("ramalama.hw_detect.importlib.import_module", side_effect=ImportError),
        ):
            result = AmdRocmDetector().detect()
        assert result == []

    def test_arm64_returns_empty(self):
        with patch("ramalama.hw_detect.platform.machine", return_value="aarch64"):
            result = AmdRocmDetector().detect()
        assert result == []


class TestDetectIntelLinux:
    @staticmethod
    def _xe_glob(pattern):
        if "xe" in pattern:
            return ["/sys/bus/pci/drivers/xe/0000:03:00.0/device"]
        return []

    def test_known_device_id(self):
        with patch("ramalama.hw_detect.glob.glob", side_effect=self._xe_glob):
            mock_file = MagicMock()
            mock_file.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value="0xe20b\n")))
            mock_file.__exit__ = MagicMock(return_value=False)
            with patch("builtins.open", return_value=mock_file):
                result = IntelDetector()._detect_linux()

        assert len(result) == 1
        assert result[0].name == "Intel Arc B580"
        assert result[0].memory_bytes == 12 * 1024**3

    def test_multi_gpu_returns_all(self):
        def multi_glob(pattern):
            if "xe" in pattern:
                return [
                    "/sys/bus/pci/drivers/xe/0000:03:00.0/device",
                    "/sys/bus/pci/drivers/xe/0000:04:00.0/device",
                ]
            return []

        device_ids = {"0000:03:00.0": "0xe20b\n", "0000:04:00.0": "0x56a1\n"}

        with patch("ramalama.hw_detect.glob.glob", side_effect=multi_glob):

            def fake_open(fp, *a, **kw):
                slot = fp.split("/")[-2]
                mock_file = MagicMock()
                mock_file.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=device_ids[slot])))
                mock_file.__exit__ = MagicMock(return_value=False)
                return mock_file

            with patch("builtins.open", side_effect=fake_open):
                result = IntelDetector()._detect_linux()

        assert len(result) == 2
        assert result[0].name == "Intel Arc B580"
        assert result[1].name == "Intel Arc A750"

    def test_unknown_device_id(self):
        with patch("ramalama.hw_detect.glob.glob", side_effect=self._xe_glob):
            mock_file = MagicMock()
            mock_file.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value="0x9999\n")))
            mock_file.__exit__ = MagicMock(return_value=False)
            with patch("builtins.open", return_value=mock_file):
                result = IntelDetector()._detect_linux()

        assert result == []

    def test_no_driver_loaded(self):
        with patch("ramalama.hw_detect.glob.glob", return_value=[]):
            result = IntelDetector()._detect_linux()
        assert result == []


class TestDetectAppleSilicon:
    def test_macos(self):
        mem_result = MagicMock()
        mem_result.stdout = "34359738368\n"
        brand_result = MagicMock()
        brand_result.stdout = "Apple M2 Pro\n"

        with (
            patch("ramalama.hw_detect.platform.system", return_value="Darwin"),
            patch("ramalama.hw_detect.subprocess.run", side_effect=[mem_result, brand_result]),
        ):
            result = AppleSiliconDetector().detect()

        assert len(result) == 1
        assert result[0].name == "Apple M2 Pro"
        assert result[0].memory_bytes == 34359738368

    def test_not_macos(self):
        with patch("ramalama.hw_detect.platform.system", return_value="Linux"):
            result = AppleSiliconDetector().detect()
        assert result == []


class TestDetectCpu:
    def test_linux_with_model_name(self):
        cpuinfo = "processor\t: 0\nmodel name\t: AMD Ryzen 7 5800X\nstepping\t: 2\n"
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=iter(cpuinfo.splitlines(keepends=True)))
        mock_file.__exit__ = MagicMock(return_value=False)

        with (
            patch("ramalama.hw_detect.platform.system", return_value="Linux"),
            patch("ramalama.hw_detect.os.sysconf", side_effect=[4096, 8388608]),
            patch("builtins.open", return_value=mock_file),
        ):
            result = CpuDetector().detect()

        assert len(result) == 1
        assert result[0].name == "AMD Ryzen 7 5800X"
        assert result[0].memory_bytes == 4096 * 8388608

    def test_windows_registry_brand(self):
        mock_key = MagicMock()
        mock_winreg = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.QueryValueEx.return_value = ("Intel(R) Core(TM) i9-13900K", 1)

        with (
            patch("ramalama.hw_detect.platform.system", return_value="Windows"),
            patch("ramalama.hw_detect._get_system_memory", return_value=34359738368),
            patch("ramalama.hw_detect.importlib.import_module", return_value=mock_winreg),
        ):
            result = CpuDetector().detect()

        assert len(result) == 1
        assert result[0].name == "Intel(R) Core(TM) i9-13900K"
        mock_winreg.CloseKey.assert_called_once_with(mock_key)

    def test_fallback_name(self):
        with (
            patch("ramalama.hw_detect.platform.system", return_value="Linux"),
            patch("ramalama.hw_detect.os.sysconf", side_effect=[4096, 8388608]),
            patch("builtins.open", side_effect=OSError),
            patch("ramalama.hw_detect.platform.processor", return_value=""),
        ):
            result = CpuDetector().detect()

        assert len(result) == 1
        assert result[0].name == "CPU"
        assert result[0].memory_bytes == 4096 * 8388608


class TestGetSystemMemory:
    def test_linux(self):
        with (
            patch("ramalama.hw_detect.platform.system", return_value="Linux"),
            patch("ramalama.hw_detect.os.sysconf", side_effect=[4096, 4194304]),
        ):
            result = _get_system_memory()
        assert result == 4096 * 4194304

    def test_darwin(self):
        mock_result = MagicMock()
        mock_result.stdout = "17179869184\n"
        with (
            patch("ramalama.hw_detect.platform.system", return_value="Darwin"),
            patch("ramalama.hw_detect.os.sysconf", side_effect=ValueError),
            patch("ramalama.hw_detect.subprocess.run", return_value=mock_result),
        ):
            result = _get_system_memory()
        assert result == 17179869184


class TestDetectAsahi:
    def test_apple_arm_platform(self):
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=b"apple,arm-platform\0")))
        mock_file.__exit__ = MagicMock(return_value=False)

        with (
            patch("builtins.open", return_value=mock_file),
            patch("ramalama.hw_detect._get_system_memory", return_value=16 * 1024**3),
            patch("ramalama.hw_detect.platform.system", return_value="Linux"),
            patch("ramalama.hw_detect.platform.processor", return_value=""),
        ):
            result = AsahiDetector().detect()

        assert len(result) == 1
        assert result[0].name == "Apple (Asahi)"
        assert result[0].memory_bytes == 16 * 1024**3

    def test_not_apple_platform(self):
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=b"some,other-platform\0")))
        mock_file.__exit__ = MagicMock(return_value=False)

        with patch("builtins.open", return_value=mock_file):
            result = AsahiDetector().detect()

        assert result == []

    def test_no_device_tree(self):
        with patch("builtins.open", side_effect=OSError):
            result = AsahiDetector().detect()
        assert result == []


class TestDetectAscend:
    NPU_SMI_OUTPUT = """\
+------------------------------------------------------------------------------------------------+
| npu-smi 24.1.rc2                 Version: 24.1.rc2                                             |
+---------------------------+---------------+----------------------------------------------------+
| NPU   Name                | Health        | Power(W)    Temp(C)           Hugepages-Usage(page)|
| Chip                      | Bus-Id        | AICore(%)   Memory-Usage(MB)  HBM-Usage(MB)        |
+===========================+===============+====================================================+
| 0     910B3               | OK            | 92.2        42                0    / 0              |
| 0                         | 0000:C1:00.0  | 0           1070 / 15079      3318 / 65536          |
+===========================+===============+====================================================+
"""

    NPU_SMI_MULTI_OUTPUT = """\
+------------------------------------------------------------------------------------------------+
| 0     910B3               | OK            | 92.2        42                0    / 0              |
| 0                         | 0000:C1:00.0  | 0           1070 / 15079      3318 / 65536          |
+===========================+===============+====================================================+
| 1     910B3               | OK            | 88.0        40                0    / 0              |
| 0                         | 0000:C2:00.0  | 0           900 / 15079       2000 / 65536          |
+===========================+===============+====================================================+
"""

    def test_parse_npu_smi(self):
        mock_result = MagicMock()
        mock_result.stdout = self.NPU_SMI_OUTPUT
        with patch("ramalama.hw_detect.subprocess.run", return_value=mock_result):
            result = AscendDetector().detect()

        assert len(result) == 1
        assert result[0].name == "Ascend 910B3"
        assert result[0].memory_bytes == 65536 * 1024 * 1024

    def test_multi_npu(self):
        mock_result = MagicMock()
        mock_result.stdout = self.NPU_SMI_MULTI_OUTPUT
        with patch("ramalama.hw_detect.subprocess.run", return_value=mock_result):
            result = AscendDetector().detect()

        assert len(result) == 2
        assert result[0].name == "Ascend 910B3"
        assert result[1].name == "Ascend 910B3"

    def test_npu_smi_not_found(self):
        with patch("ramalama.hw_detect.subprocess.run", side_effect=OSError):
            result = AscendDetector().detect()
        assert result == []

    def test_npu_smi_fails(self):
        with patch("ramalama.hw_detect.subprocess.run", side_effect=subprocess.CalledProcessError(1, "npu-smi")):
            result = AscendDetector().detect()
        assert result == []


class TestDetectMthreads:
    MTHREADS_JSON = """{
        "Driver Version": "2.7.0",
        "GPU": [
            {
                "Index": "0",
                "Product Name": "MTT S4000",
                "FB Memory Usage": {
                    "Total": "49152MiB",
                    "Used": "1339MiB",
                    "Free": "47813MiB"
                }
            }
        ]
    }"""

    def test_parse_json(self):
        mock_result = MagicMock()
        mock_result.stdout = self.MTHREADS_JSON
        with patch("ramalama.hw_detect.subprocess.run", return_value=mock_result):
            result = MthreadsDetector().detect()

        assert len(result) == 1
        assert result[0].name == "MTT S4000"
        assert result[0].memory_bytes == 49152 * 1024 * 1024

    def test_multi_gpu_returns_all(self):
        data = {
            "GPU": [
                {"Product Name": "MTT S80", "FB Memory Usage": {"Total": "16384MiB"}},
                {"Product Name": "MTT S4000", "FB Memory Usage": {"Total": "49152MiB"}},
            ]
        }
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(data)
        with patch("ramalama.hw_detect.subprocess.run", return_value=mock_result):
            result = MthreadsDetector().detect()

        assert len(result) == 2
        assert result[0].name == "MTT S80"
        assert result[0].memory_bytes == 16384 * 1024 * 1024
        assert result[1].name == "MTT S4000"
        assert result[1].memory_bytes == 49152 * 1024 * 1024

    def test_not_found(self):
        with patch("ramalama.hw_detect.subprocess.run", side_effect=OSError):
            result = MthreadsDetector().detect()
        assert result == []

    def test_invalid_json(self):
        mock_result = MagicMock()
        mock_result.stdout = "not json"
        with patch("ramalama.hw_detect.subprocess.run", return_value=mock_result):
            result = MthreadsDetector().detect()
        assert result == []


class TestParseMemoryString:
    def test_mib(self):
        assert MthreadsDetector._parse_memory_string("49152MiB") == 49152 * 1024 * 1024

    def test_gib(self):
        assert MthreadsDetector._parse_memory_string("16GiB") == 16 * 1024 * 1024 * 1024

    def test_mb(self):
        assert MthreadsDetector._parse_memory_string("8000MB") == 8000 * 1000 * 1000

    def test_plain_number(self):
        assert MthreadsDetector._parse_memory_string("1024") == 1024

    def test_invalid(self):
        assert MthreadsDetector._parse_memory_string("unknown") == 0


class TestDetectVulkan:
    VK_DISCRETE = 2

    def test_discrete_gpu(self):
        raw = [
            _VulkanDeviceRaw(
                "AMD Radeon RX 7900 XTX",
                self.VK_DISCRETE,
                [
                    (25149440000, VK_MEMORY_HEAP_DEVICE_LOCAL_BIT),
                    (16768487424, 0),
                ],
            )
        ]
        with patch("ramalama.hw_detect._query_vulkan_devices", return_value=raw):
            result = VulkanDetector().detect()

        assert len(result) == 1
        assert result[0].name == "AMD Radeon RX 7900 XTX"
        assert result[0].memory_bytes == 25149440000

    def test_multi_gpu_returns_all(self):
        raw = [
            _VulkanDeviceRaw(
                "AMD Radeon RX 7900 XTX",
                self.VK_DISCRETE,
                [
                    (25149440000, VK_MEMORY_HEAP_DEVICE_LOCAL_BIT),
                ],
            ),
            _VulkanDeviceRaw(
                "AMD Radeon RX 7600",
                self.VK_DISCRETE,
                [
                    (8522825728, VK_MEMORY_HEAP_DEVICE_LOCAL_BIT),
                ],
            ),
        ]
        with patch("ramalama.hw_detect._query_vulkan_devices", return_value=raw):
            result = VulkanDetector().detect()

        assert len(result) == 2
        assert result[0].name == "AMD Radeon RX 7900 XTX"
        assert result[0].memory_bytes == 25149440000
        assert result[1].name == "AMD Radeon RX 7600"
        assert result[1].memory_bytes == 8522825728

    def test_no_vulkan_library(self):
        with patch("ramalama.hw_detect._query_vulkan_devices", side_effect=Exception("no vulkan")):
            result = VulkanDetector().detect()
        assert result == []

    def test_no_devices(self):
        with patch("ramalama.hw_detect._query_vulkan_devices", return_value=[]):
            result = VulkanDetector().detect()
        assert result == []

    def test_no_device_local_heap(self):
        raw = [
            _VulkanDeviceRaw(
                "Some GPU",
                self.VK_DISCRETE,
                [
                    (8000000000, 0),
                ],
            )
        ]
        with patch("ramalama.hw_detect._query_vulkan_devices", return_value=raw):
            result = VulkanDetector().detect()

        assert result == []

    def test_integrated_gpu_sums_all_heaps(self):
        raw = [
            _VulkanDeviceRaw(
                "AMD Radeon Graphics (RADV RENOIR)",
                VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU,
                [
                    (268435456, VK_MEMORY_HEAP_DEVICE_LOCAL_BIT),
                    (17268350976, 0),
                ],
            )
        ]
        with patch("ramalama.hw_detect._query_vulkan_devices", return_value=raw):
            result = VulkanDetector().detect()

        assert len(result) == 1
        assert result[0].name == "AMD Radeon Graphics (RADV RENOIR)"
        assert result[0].memory_bytes == 268435456 + 17268350976

    def test_software_renderer_skipped(self):
        raw = [
            _VulkanDeviceRaw(
                "AMD Radeon RX 7900 XTX",
                self.VK_DISCRETE,
                [
                    (25149440000, VK_MEMORY_HEAP_DEVICE_LOCAL_BIT),
                ],
            ),
            _VulkanDeviceRaw(
                "llvmpipe (LLVM 21.1.8, 256 bits)",
                VK_PHYSICAL_DEVICE_TYPE_CPU,
                [
                    (33030258688, VK_MEMORY_HEAP_DEVICE_LOCAL_BIT),
                ],
            ),
        ]
        with patch("ramalama.hw_detect._query_vulkan_devices", return_value=raw):
            result = VulkanDetector().detect()

        assert len(result) == 1
        assert result[0].name == "AMD Radeon RX 7900 XTX"


def _patch_all_detectors_empty():
    """Context manager that patches all per-detector functions to return []."""
    from contextlib import ExitStack

    stack = ExitStack()
    for name in [
        "detect_asahi",
        "detect_nvidia",
        "detect_ascend",
        "detect_amd_rocm",
        "detect_intel",
        "detect_mthreads",
        "detect_apple_silicon",
        "detect_vulkan",
    ]:
        stack.enter_context(patch(f"ramalama.hw_detect.{name}", return_value=[]))
    return stack


class TestDetectAllHardware:
    def test_collects_all_types(self):
        nvidia_devices = [DeviceInfo("RTX 4090", 24 * 1024**3)]
        amd_devices = [DeviceInfo("AMD Renoir", 8 * 1024**3)]

        with (
            _patch_all_detectors_empty(),
            patch("ramalama.hw_detect.detect_nvidia", return_value=nvidia_devices),
            patch("ramalama.hw_detect.detect_amd_rocm", return_value=amd_devices),
            patch("ramalama.hw_detect._get_system_memory", return_value=32 * 1024**3),
            patch.object(CpuDetector, "_get_cpu_name", return_value=""),
        ):
            result = detect_all_hardware()

        types = [acc.accel_type for acc in result]
        assert "cuda" in types
        assert "hip" in types
        assert "cpu" in types

    def test_cpu_always_present(self):
        with (
            _patch_all_detectors_empty(),
            patch("ramalama.hw_detect._get_system_memory", return_value=16 * 1024**3),
            patch.object(CpuDetector, "_get_cpu_name", return_value=""),
        ):
            result = detect_all_hardware()

        assert len(result) == 1
        assert result[0].accel_type == "cpu"
        assert result[0].devices[0].name == "CPU"

    def test_total_memory_summed(self):
        nvidia_devices = [
            DeviceInfo("RTX 4090", 24 * 1024**3),
            DeviceInfo("RTX 4090", 24 * 1024**3),
        ]

        with (
            _patch_all_detectors_empty(),
            patch("ramalama.hw_detect.detect_nvidia", return_value=nvidia_devices),
            patch("ramalama.hw_detect._get_system_memory", return_value=32 * 1024**3),
            patch.object(CpuDetector, "_get_cpu_name", return_value=""),
        ):
            result = detect_all_hardware()

        cuda_acc = next(acc for acc in result if acc.accel_type == "cuda")
        assert cuda_acc.total_memory_bytes == 48 * 1024**3
        assert len(cuda_acc.devices) == 2

    def test_detector_exception_continues(self):
        amd_devices = [DeviceInfo("AMD Renoir", 8 * 1024**3)]
        with (
            _patch_all_detectors_empty(),
            patch("ramalama.hw_detect.detect_nvidia", side_effect=RuntimeError("boom")),
            patch("ramalama.hw_detect.detect_amd_rocm", return_value=amd_devices),
            patch("ramalama.hw_detect._get_system_memory", return_value=16 * 1024**3),
            patch.object(CpuDetector, "_get_cpu_name", return_value=""),
        ):
            result = detect_all_hardware()

        types = [acc.accel_type for acc in result]
        assert "cuda" not in types
        assert "hip" in types
        assert "cpu" in types


class TestIntelGpuSpecs:
    def test_all_battlemage_present(self):
        assert "0xe20b" in INTEL_GPU_SPECS
        assert "0xe20c" in INTEL_GPU_SPECS
        assert "0xe212" in INTEL_GPU_SPECS
        assert "0xe211" in INTEL_GPU_SPECS

    def test_all_alchemist_desktop_present(self):
        assert "0x56a0" in INTEL_GPU_SPECS
        assert "0x56a1" in INTEL_GPU_SPECS
        assert "0x56a2" in INTEL_GPU_SPECS
        assert "0x56a5" in INTEL_GPU_SPECS
        assert "0x56a6" in INTEL_GPU_SPECS

    @pytest.mark.parametrize(
        "device_id,expected_name",
        [
            ("0xe20b", "Intel Arc B580"),
            ("0x56a0", "Intel Arc A770"),
            ("0x56a1", "Intel Arc A750"),
        ],
    )
    def test_device_id_to_name(self, device_id, expected_name):
        name, _ = INTEL_GPU_SPECS[device_id]
        assert name == expected_name
