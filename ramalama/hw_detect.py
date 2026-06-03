from __future__ import annotations

import glob
import importlib
import os
import platform
import re
import struct
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from ramalama.logger import logger

GiB = 1024 * 1024 * 1024


@dataclass
class DeviceInfo:
    name: str
    memory_bytes: int
    index: int = 0
    uuid: str = ""


@dataclass
class AcceleratorInfo:
    accel_type: str
    devices: list[DeviceInfo] = field(default_factory=list)
    total_memory_bytes: int = 0


# Intel GPU PCI device IDs → (name, VRAM in bytes)
# Source: https://dgpu-docs.intel.com/devices/hardware-table.html
INTEL_GPU_SPECS: dict[str, tuple[str, int]] = {
    # Battlemage (Xe2)
    "0xe20b": ("Intel Arc B580", 12 * GiB),
    "0xe20c": ("Intel Arc B570", 10 * GiB),
    "0xe212": ("Intel Arc Pro B50", 16 * GiB),
    "0xe211": ("Intel Arc Pro B60", 24 * GiB),
    # Alchemist (Xe-HPG) desktop
    "0x56a0": ("Intel Arc A770", 16 * GiB),
    "0x56a1": ("Intel Arc A750", 8 * GiB),
    "0x56a2": ("Intel Arc A580", 8 * GiB),
    "0x56a5": ("Intel Arc A380", 6 * GiB),
    "0x56a6": ("Intel Arc A310", 4 * GiB),
    # Alchemist (Xe-HPG) mobile
    "0x5690": ("Intel Arc A770M", 16 * GiB),
    "0x5691": ("Intel Arc A730M", 12 * GiB),
    "0x5692": ("Intel Arc A550M", 8 * GiB),
    "0x5693": ("Intel Arc A370M", 4 * GiB),
    "0x5694": ("Intel Arc A350M", 4 * GiB),
    "0x5696": ("Intel Arc A570M", 8 * GiB),
    "0x5697": ("Intel Arc A530M", 8 * GiB),
    # Alchemist Pro
    "0x56b0": ("Intel Arc Pro A30M", 4 * GiB),
    "0x56b1": ("Intel Arc Pro A40/A50", 6 * GiB),
    "0x56b2": ("Intel Arc Pro A60M", 8 * GiB),
    "0x56b3": ("Intel Arc Pro A60", 16 * GiB),
    # Alchemist embedded
    "0x56ba": ("Intel Arc A380E", 6 * GiB),
    "0x56bb": ("Intel Arc A310E", 4 * GiB),
    "0x56bc": ("Intel Arc A370E", 4 * GiB),
    "0x56bd": ("Intel Arc A350E", 4 * GiB),
    # Integrated GPUs (Xe-LP / Xe-LPG) — VRAM is shared system memory
    "0x46a6": ("Intel Alder Lake-P Graphics", 0),
    "0x46a8": ("Intel Alder Lake-P Graphics", 0),
    "0x46aa": ("Intel Alder Lake-P Graphics", 0),
    "0x7d51": ("Intel Raptor Lake-P Graphics", 0),
    "0x7d55": ("Intel Raptor Lake-P Graphics", 0),
    "0x7dd5": ("Intel Raptor Lake-P Graphics", 0),
}


_PCI_IDS_PATHS = ["/usr/share/hwdata/pci.ids", "/usr/share/misc/pci.ids"]


@lru_cache(maxsize=64)
def _lookup_pci_device_name(vendor_id: str, device_id: str) -> Optional[str]:
    for pci_ids_path in _PCI_IDS_PATHS:
        try:
            with open(pci_ids_path, "r", errors="replace") as f:
                in_vendor = False
                for line in f:
                    if line.startswith("#") or line.strip() == "":
                        continue
                    if not line.startswith("\t"):
                        in_vendor = line.startswith(vendor_id + " ")
                        continue
                    if in_vendor and line.startswith("\t") and not line.startswith("\t\t"):
                        parts = line.strip().split("  ", 1)
                        if len(parts) == 2 and parts[0] == device_id:
                            return parts[1].strip()
        except OSError:
            continue
    return None


class HardwareDetector(ABC):
    @property
    @abstractmethod
    def accel_type(self) -> str: ...

    @abstractmethod
    def detect(self) -> list[DeviceInfo]: ...


class CpuDetector(HardwareDetector):
    @property
    def accel_type(self) -> str:
        return "cpu"

    def detect(self) -> list[DeviceInfo]:
        memory = _get_system_memory()
        name = self._get_cpu_name() or "CPU"
        return [DeviceInfo(name=name, memory_bytes=memory)]

    def _get_cpu_name(self) -> str:
        system = platform.system()

        if system == "Linux":
            try:
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if line.startswith("model name"):
                            return line.split(":", 1)[1].strip()
            except OSError:
                pass

        if system == "Darwin":
            try:
                result = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, encoding="utf-8", check=True
                )
                brand = result.stdout.strip()
                if brand:
                    return brand
            except (OSError, subprocess.CalledProcessError):
                pass

        if system == "Windows":
            try:
                winreg = importlib.import_module("winreg")
                key = getattr(winreg, "OpenKey")(
                    getattr(winreg, "HKEY_LOCAL_MACHINE"),
                    r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
                )
                try:
                    brand, _ = getattr(winreg, "QueryValueEx")(key, "ProcessorNameString")
                    if brand and isinstance(brand, str):
                        return brand.strip()
                finally:
                    getattr(winreg, "CloseKey")(key)
            except Exception:
                pass

        name = platform.processor()
        if name:
            return name

        return ""


class AsahiDetector(CpuDetector):
    @property
    def accel_type(self) -> str:
        return "asahi"

    def detect(self) -> list[DeviceInfo]:
        try:
            with open("/proc/device-tree/compatible", "rb") as f:
                content = f.read().split(b"\0")
        except OSError:
            return []

        if b"apple,arm-platform" not in content:
            return []

        devices = super().detect()
        if devices:
            devices[0] = DeviceInfo(name="Apple (Asahi)", memory_bytes=devices[0].memory_bytes)
        return devices


class NvidiaDetector(HardwareDetector):
    @property
    def accel_type(self) -> str:
        return "cuda"

    def detect(self) -> list[DeviceInfo]:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,uuid,memory.total,name", "--format=csv,noheader,nounits"],
                capture_output=True,
                encoding="utf-8",
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return []

        devices: list[DeviceInfo] = []
        for line in result.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",", 3)]
            if len(parts) != 4:
                continue
            try:
                idx = int(parts[0])
                memory_mib = int(parts[2])
            except ValueError:
                continue
            devices.append(DeviceInfo(name=parts[3], memory_bytes=memory_mib * 1024 * 1024, index=idx, uuid=parts[1]))

        return devices


class AscendDetector(HardwareDetector):
    @property
    def accel_type(self) -> str:
        return "cann"

    def detect(self) -> list[DeviceInfo]:
        try:
            result = subprocess.run(["npu-smi", "info"], capture_output=True, encoding="utf-8", check=True)
        except (OSError, subprocess.CalledProcessError):
            return []

        devices: list[DeviceInfo] = []
        current_name = "Ascend NPU"
        current_memory = 0

        for line in result.stdout.splitlines():
            cells = [c.strip() for c in line.split("|")]
            if len(cells) >= 3:
                first = cells[1] if len(cells) > 1 else ""
                parts = first.split()
                if len(parts) >= 2 and parts[0].isdigit():
                    if current_memory > 0:
                        devices.append(DeviceInfo(name=current_name, memory_bytes=current_memory))
                    current_name = f"Ascend {parts[1]}"
                    current_memory = 0

            for match in re.finditer(r"(\d+)\s*/\s*(\d+)", line):
                try:
                    total_mb = int(match.group(2))
                    total_bytes = total_mb * 1024 * 1024
                    if total_bytes > current_memory:
                        current_memory = total_bytes
                except ValueError:
                    continue

        if current_memory > 0:
            devices.append(DeviceInfo(name=current_name, memory_bytes=current_memory))

        return devices


class AmdRocmDetector(HardwareDetector):
    @property
    def accel_type(self) -> str:
        return "hip"

    def detect(self) -> list[DeviceInfo]:
        if platform.machine() in ("arm64", "aarch64"):
            return []

        try:
            amdkfd = importlib.import_module("ramalama.amdkfd")
        except ImportError:
            return []

        devices: list[DeviceInfo] = []
        for i, (np, props) in enumerate(amdkfd.gpus()):
            if props["gfx_target_version"] < 90000:
                continue

            mem_banks_count = int(props["mem_banks_count"])
            mem_bytes = 0
            for bank in range(mem_banks_count):
                bank_props = amdkfd.parse_props(np + f"/mem_banks/{bank}/properties")
                if bank_props["heap_type"] in [amdkfd.HEAP_TYPE_FB_PUBLIC, amdkfd.HEAP_TYPE_FB_PRIVATE]:
                    mem_bytes += int(bank_props["size_in_bytes"])

            if mem_bytes > 0:
                name = ""
                try:
                    with open(np + "/name", "r") as f:
                        name = f.read().strip()
                except OSError:
                    pass
                device_id = props.get("device_id", 0)
                if name and name != "ip discovery":
                    name = f"AMD {name.capitalize()}"
                elif device_id:
                    pci_name = _lookup_pci_device_name("1002", f"{device_id:04x}")
                    name = f"AMD {pci_name}" if pci_name else f"AMD GPU (0x{device_id:04x})"
                else:
                    name = "AMD GPU"
                devices.append(DeviceInfo(name=name, memory_bytes=mem_bytes, index=i))

        return devices


class IntelDetector(HardwareDetector):
    @property
    def accel_type(self) -> str:
        return "intel"

    def detect(self) -> list[DeviceInfo]:
        if platform.system() == "Windows":
            return self._detect_windows()
        return self._detect_linux()

    def _detect_linux(self) -> list[DeviceInfo]:
        driver_patterns = ["/sys/bus/pci/drivers/i915/*/device", "/sys/bus/pci/drivers/xe/*/device"]
        devices: list[DeviceInfo] = []
        for fp in sorted(i for p in driver_patterns for i in glob.glob(p)):
            try:
                with open(fp, "r") as f:
                    device_id = f.read().strip().lower()
            except OSError:
                continue

            if device_id in INTEL_GPU_SPECS:
                gpu_name, vram = INTEL_GPU_SPECS[device_id]
                devices.append(DeviceInfo(name=gpu_name, memory_bytes=vram))

        return devices

    def _detect_windows(self) -> list[DeviceInfo]:
        devices: list[DeviceInfo] = []
        try:
            import wmi  # type: ignore

            w = wmi.WMI()
            for gpu in w.Win32_VideoController():
                gpu_name = gpu.Name or ""
                if "intel" not in gpu_name.lower():
                    continue
                if "arc" not in gpu_name.lower():
                    continue

                memory = self._read_windows_vram(gpu.PNPDeviceID)
                if memory is None or memory == 0:
                    memory = gpu.AdapterRAM or 0
                if memory > 0:
                    devices.append(DeviceInfo(name=gpu_name, memory_bytes=memory))
        except Exception as e:
            logger.debug(f"Intel Windows detection failed: {e}")

        return devices

    @staticmethod
    def _read_windows_vram(pnp_device_id: Optional[str]) -> Optional[int]:
        if pnp_device_id is None:
            return None

        try:
            import importlib as _il

            winreg = _il.import_module("winreg")

            video_class_key = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
            hklm = getattr(winreg, "HKEY_LOCAL_MACHINE")
            open_key = getattr(winreg, "OpenKey")
            enum_key = getattr(winreg, "EnumKey")
            query_value = getattr(winreg, "QueryValueEx")

            with open_key(hklm, video_class_key) as class_key:
                i = 0
                while True:
                    try:
                        subkey_name = enum_key(class_key, i)
                        i += 1
                    except OSError:
                        break

                    try:
                        with open_key(class_key, subkey_name) as subkey:
                            matching_id, _ = query_value(subkey, "MatchingDeviceId")
                            if not isinstance(matching_id, str):
                                continue

                            pnp_lower = pnp_device_id.lower()
                            matching_lower = matching_id.lower()
                            if (
                                matching_lower not in pnp_lower
                                and pnp_lower.split("\\")[0:2] != matching_lower.split("\\")[0:2]
                            ):
                                continue

                            qw_mem, reg_type = query_value(subkey, "HardwareInformation.qwMemorySize")
                            if isinstance(qw_mem, bytes) and len(qw_mem) == 8:
                                return struct.unpack("<Q", qw_mem)[0]
                            if isinstance(qw_mem, int):
                                return qw_mem
                    except OSError:
                        continue
        except Exception as e:
            logger.debug(f"Windows registry VRAM read failed: {e}")

        return None


class MthreadsDetector(HardwareDetector):
    @property
    def accel_type(self) -> str:
        return "musa"

    def detect(self) -> list[DeviceInfo]:
        try:
            result = subprocess.run(["mthreads-gmi", "-q", "--json"], capture_output=True, encoding="utf-8", check=True)
        except (OSError, subprocess.CalledProcessError):
            return []

        try:
            import json

            data = json.loads(result.stdout)
        except (ValueError, KeyError):
            return []

        devices: list[DeviceInfo] = []
        for gpu in data.get("GPU", []):
            name = gpu.get("Product Name", "Moore Threads GPU")
            total_str = gpu.get("FB Memory Usage", {}).get("Total", "")
            total_bytes = self._parse_memory_string(total_str)
            if total_bytes > 0:
                devices.append(DeviceInfo(name=name or "Moore Threads GPU", memory_bytes=total_bytes))

        return devices

    @staticmethod
    def _parse_memory_string(s: str) -> int:
        s = s.strip().upper()
        try:
            if s.endswith("GIB"):
                return int(float(s[:-3]) * GiB)
            if s.endswith("MIB"):
                return int(float(s[:-3]) * 1024 * 1024)
            if s.endswith("KIB"):
                return int(float(s[:-3]) * 1024)
            if s.endswith("GB"):
                return int(float(s[:-2]) * 1000 * 1000 * 1000)
            if s.endswith("MB"):
                return int(float(s[:-2]) * 1000 * 1000)
            return int(s)
        except ValueError:
            return 0


class AppleSiliconDetector(HardwareDetector):
    @property
    def accel_type(self) -> str:
        return "metal"

    def detect(self) -> list[DeviceInfo]:
        if platform.system() != "Darwin":
            return []

        try:
            result = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, encoding="utf-8", check=True)
            total_mem = int(result.stdout.strip())
        except (OSError, subprocess.CalledProcessError, ValueError):
            return []

        name = "Apple Silicon"
        try:
            brand_result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, encoding="utf-8", check=True
            )
            brand = brand_result.stdout.strip()
            if brand:
                name = brand
        except (OSError, subprocess.CalledProcessError):
            pass

        return [DeviceInfo(name=name, memory_bytes=total_mem)]


VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU = 1
VK_PHYSICAL_DEVICE_TYPE_CPU = 4
VK_MEMORY_HEAP_DEVICE_LOCAL_BIT = 0x1
VK_MAX_PHYSICAL_DEVICE_NAME_SIZE = 256
VK_SUCCESS = 0


@dataclass
class _VulkanDeviceRaw:
    name: str
    device_type: int
    heaps: list[tuple[int, int]]  # (size, flags)


def _query_vulkan_devices() -> list[_VulkanDeviceRaw]:
    # Suppress stderr during Vulkan API calls — some drivers (e.g. RADV) emit
    # non-conformance warnings that are harmless for device enumeration.
    try:
        saved_stderr = os.dup(2)
    except OSError:
        return _query_vulkan_devices_inner()
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 2)
        os.close(devnull)
        return _query_vulkan_devices_inner()
    finally:
        os.dup2(saved_stderr, 2)
        os.close(saved_stderr)


def _query_vulkan_devices_inner() -> list[_VulkanDeviceRaw]:
    import ctypes as ct
    import ctypes.util

    is_windows = platform.system() == "Windows"
    loader_class = ct.WinDLL if is_windows else ct.CDLL  # type: ignore[attr-defined]

    lib = None
    for name in ["vulkan", "vulkan-1"]:
        path = ct.util.find_library(name)
        if path:
            try:
                lib = loader_class(path)
                break
            except OSError:
                continue

    if lib is None:
        fallbacks = ["vulkan-1.dll"] if is_windows else ["libvulkan.so.1", "libvulkan.so"]
        for path in fallbacks:
            try:
                lib = loader_class(path)
                break
            except OSError:
                continue

    if lib is None:
        return []

    class VkApplicationInfo(ct.Structure):
        _fields_ = [
            ("sType", ct.c_uint32),
            ("pNext", ct.c_void_p),
            ("pApplicationName", ct.c_char_p),
            ("applicationVersion", ct.c_uint32),
            ("pEngineName", ct.c_char_p),
            ("engineVersion", ct.c_uint32),
            ("apiVersion", ct.c_uint32),
        ]

    class VkInstanceCreateInfo(ct.Structure):
        _fields_ = [
            ("sType", ct.c_uint32),
            ("pNext", ct.c_void_p),
            ("flags", ct.c_uint32),
            ("pApplicationInfo", ct.POINTER(VkApplicationInfo)),
            ("enabledLayerCount", ct.c_uint32),
            ("ppEnabledLayerNames", ct.c_void_p),
            ("enabledExtensionCount", ct.c_uint32),
            ("ppEnabledExtensionNames", ct.c_void_p),
        ]

    class VkPhysicalDeviceProperties(ct.Structure):
        _fields_ = [
            ("apiVersion", ct.c_uint32),
            ("driverVersion", ct.c_uint32),
            ("vendorID", ct.c_uint32),
            ("deviceID", ct.c_uint32),
            ("deviceType", ct.c_uint32),
            ("deviceName", ct.c_char * VK_MAX_PHYSICAL_DEVICE_NAME_SIZE),
            # pipelineCacheUUID(16) + padding(4) + VkPhysicalDeviceLimits(504) +
            # VkPhysicalDeviceSparseProperties(20) = 544. Total: 20+256+544 = 820.
            # Actual struct is 824 due to trailing alignment; pad to 824 - 20 - 256 = 548.
            ("_tail", ct.c_uint8 * 548),
        ]

    class VkMemoryHeap(ct.Structure):
        _fields_ = [
            ("size", ct.c_uint64),
            ("flags", ct.c_uint32),
        ]

    VK_MAX_MEMORY_TYPES = 32
    VK_MAX_MEMORY_HEAPS = 16

    class VkMemoryType(ct.Structure):
        _fields_ = [
            ("propertyFlags", ct.c_uint32),
            ("heapIndex", ct.c_uint32),
        ]

    class VkPhysicalDeviceMemoryProperties(ct.Structure):
        _fields_ = [
            ("memoryTypeCount", ct.c_uint32),
            ("memoryTypes", VkMemoryType * VK_MAX_MEMORY_TYPES),
            ("memoryHeapCount", ct.c_uint32),
            ("memoryHeaps", VkMemoryHeap * VK_MAX_MEMORY_HEAPS),
        ]

    VkInstance = ct.c_void_p
    VkPhysicalDevice = ct.c_void_p

    lib.vkCreateInstance.restype = ct.c_int32
    lib.vkCreateInstance.argtypes = [ct.POINTER(VkInstanceCreateInfo), ct.c_void_p, ct.POINTER(VkInstance)]

    lib.vkDestroyInstance.restype = None
    lib.vkDestroyInstance.argtypes = [VkInstance, ct.c_void_p]

    lib.vkEnumeratePhysicalDevices.restype = ct.c_int32
    lib.vkEnumeratePhysicalDevices.argtypes = [VkInstance, ct.POINTER(ct.c_uint32), ct.c_void_p]

    lib.vkGetPhysicalDeviceProperties.restype = None
    lib.vkGetPhysicalDeviceProperties.argtypes = [VkPhysicalDevice, ct.POINTER(VkPhysicalDeviceProperties)]

    lib.vkGetPhysicalDeviceMemoryProperties.restype = None
    lib.vkGetPhysicalDeviceMemoryProperties.argtypes = [
        VkPhysicalDevice,
        ct.POINTER(VkPhysicalDeviceMemoryProperties),
    ]

    app_info = VkApplicationInfo(
        sType=0,
        pNext=None,
        pApplicationName=b"ramalama",
        applicationVersion=1,
        pEngineName=b"ramalama",
        engineVersion=1,
        apiVersion=(1 << 22) | (0 << 12),
    )

    create_info = VkInstanceCreateInfo(
        sType=1,
        pNext=None,
        flags=0,
        pApplicationInfo=ct.pointer(app_info),
        enabledLayerCount=0,
        ppEnabledLayerNames=None,
        enabledExtensionCount=0,
        ppEnabledExtensionNames=None,
    )

    instance = VkInstance()
    result = lib.vkCreateInstance(ct.byref(create_info), None, ct.byref(instance))
    if result != VK_SUCCESS:
        return []

    try:
        count = ct.c_uint32(0)
        lib.vkEnumeratePhysicalDevices(instance, ct.byref(count), None)
        if count.value == 0:
            return []

        physical_devices = (VkPhysicalDevice * count.value)()
        lib.vkEnumeratePhysicalDevices(instance, ct.byref(count), physical_devices)

        devices: list[_VulkanDeviceRaw] = []
        for i in range(count.value):
            props = VkPhysicalDeviceProperties()
            lib.vkGetPhysicalDeviceProperties(physical_devices[i], ct.byref(props))

            name = props.deviceName.decode("utf-8", errors="replace").rstrip("\x00") or "Vulkan GPU"

            mem_props = VkPhysicalDeviceMemoryProperties()
            lib.vkGetPhysicalDeviceMemoryProperties(physical_devices[i], ct.byref(mem_props))

            heaps = [
                (mem_props.memoryHeaps[j].size, mem_props.memoryHeaps[j].flags)
                for j in range(mem_props.memoryHeapCount)
            ]
            devices.append(_VulkanDeviceRaw(name=name, device_type=props.deviceType, heaps=heaps))

        return devices
    finally:
        lib.vkDestroyInstance(instance, None)


class VulkanDetector(HardwareDetector):
    @property
    def accel_type(self) -> str:
        return "vulkan"

    def detect(self) -> list[DeviceInfo]:
        try:
            raw_devices = _query_vulkan_devices()
        except Exception:
            return []

        devices: list[DeviceInfo] = []
        for raw in raw_devices:
            if raw.device_type == VK_PHYSICAL_DEVICE_TYPE_CPU:
                continue

            is_integrated = raw.device_type == VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU

            total_mem = 0
            for size, flags in raw.heaps:
                if is_integrated or (flags & VK_MEMORY_HEAP_DEVICE_LOCAL_BIT):
                    total_mem += size

            if total_mem > 0:
                devices.append(DeviceInfo(name=raw.name, memory_bytes=total_mem))

        return devices


def _get_system_memory() -> int:
    system = platform.system()

    if system == "Linux":
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            page_count = os.sysconf("SC_PHYS_PAGES")
            if page_size > 0 and page_count > 0:
                return page_size * page_count
        except (ValueError, OSError):
            pass

    if system == "Darwin":
        try:
            result = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, encoding="utf-8", check=True)
            return int(result.stdout.strip())
        except (OSError, subprocess.CalledProcessError, ValueError):
            pass

    if system == "Windows":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))  # type: ignore
            return stat.ullTotalPhys
        except Exception:
            pass

    return 0


@lru_cache(maxsize=1)
def detect_asahi() -> list[DeviceInfo]:
    return AsahiDetector().detect()


@lru_cache(maxsize=1)
def detect_nvidia() -> list[DeviceInfo]:
    return NvidiaDetector().detect()


@lru_cache(maxsize=1)
def detect_ascend() -> list[DeviceInfo]:
    return AscendDetector().detect()


@lru_cache(maxsize=1)
def detect_amd_rocm() -> list[DeviceInfo]:
    return AmdRocmDetector().detect()


@lru_cache(maxsize=1)
def detect_intel() -> list[DeviceInfo]:
    return IntelDetector().detect()


@lru_cache(maxsize=1)
def detect_mthreads() -> list[DeviceInfo]:
    return MthreadsDetector().detect()


@lru_cache(maxsize=1)
def detect_apple_silicon() -> list[DeviceInfo]:
    return AppleSiliconDetector().detect()


@lru_cache(maxsize=1)
def detect_vulkan() -> list[DeviceInfo]:
    return VulkanDetector().detect()


_DETECTOR_NAMES: list[tuple[str, str]] = [
    ("asahi", "detect_asahi"),
    ("cuda", "detect_nvidia"),
    ("cann", "detect_ascend"),
    ("hip", "detect_amd_rocm"),
    ("intel", "detect_intel"),
    ("musa", "detect_mthreads"),
    ("metal", "detect_apple_silicon"),
    ("vulkan", "detect_vulkan"),
]


def clear_all_detection_caches() -> None:
    detect_asahi.cache_clear()
    detect_nvidia.cache_clear()
    detect_ascend.cache_clear()
    detect_amd_rocm.cache_clear()
    detect_intel.cache_clear()
    detect_mthreads.cache_clear()
    detect_apple_silicon.cache_clear()
    detect_vulkan.cache_clear()
    detect_all_hardware.cache_clear()


@lru_cache(maxsize=1)
def detect_all_hardware() -> tuple[AcceleratorInfo, ...]:
    import ramalama.hw_detect as _self

    results: list[AcceleratorInfo] = []
    for accel_type, fn_name in _DETECTOR_NAMES:
        try:
            fn: Callable[[], list[DeviceInfo]] = getattr(_self, fn_name)
            devices = fn()
            if devices:
                total = sum(d.memory_bytes for d in devices)
                results.append(AcceleratorInfo(accel_type=accel_type, devices=devices, total_memory_bytes=total))
        except Exception as e:
            logger.debug(f"Hardware detection failed for {accel_type}: {e}")

    cpu = CpuDetector()
    cpu_devices = cpu.detect()
    results.append(
        AcceleratorInfo(
            accel_type="cpu",
            devices=cpu_devices,
            total_memory_bytes=sum(d.memory_bytes for d in cpu_devices),
        )
    )
    return tuple(results)
