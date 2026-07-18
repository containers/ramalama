"""Hardware detection and profile structures for automated image selection."""

from __future__ import annotations

import glob
import platform
import re
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TypeAlias

import ramalama.amdkfd as amdkfd
from ramalama.version_constraints import Version

if TYPE_CHECKING:
    pass

Architecture: TypeAlias = Literal["x86_64", "aarch64"]
GpuType: TypeAlias = Literal["cuda", "hip", "intel", "asahi", "cann", "musa", "vulkan", "metal", "none"]
OsType: TypeAlias = Literal["linux", "darwin", "windows"]

_ALLOWED_EXECUTABLES = frozenset({
    "nvidia-smi",
    "rocm-smi",
    "rocminfo",
    "npu-smi",
    "mthreads-gmi",
})


@dataclass
class GpuInfo:
    """Information about detected GPU hardware."""

    gpu_type: GpuType
    driver_version: Version | None = None
    device_count: int = 0
    memory_bytes: int = 0
    device_ids: list[str] = field(default_factory=list)
    gfx_version: int = 0  # For AMD GPUs, the gfx target version


@dataclass
class HardwareProfile:
    """Complete hardware profile for image selection."""

    architecture: Architecture
    gpu: GpuInfo
    is_container: bool = False
    os_type: OsType = "linux"

    def __post_init__(self):
        # Normalize arm64 to aarch64
        if self.architecture == "arm64":  # type: ignore[comparison-overlap]
            object.__setattr__(self, "architecture", "aarch64")


def get_architecture() -> Architecture:
    """Get the current system architecture."""
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "x86_64"
    elif machine in ("arm64", "aarch64"):
        return "aarch64"
    # Default to x86_64 for unknown architectures
    return "x86_64"


def get_os_type() -> OsType:
    """Get the current operating system type."""
    system = platform.system().lower()
    if system == "darwin":
        return "darwin"
    elif system == "windows":
        return "windows"
    return "linux"


def is_arm() -> bool:
    """Check if the system is ARM architecture."""
    return get_architecture() == "aarch64"


def _run_cmd(args: list[str], encoding: str = "utf-8") -> subprocess.CompletedProcess[str]:
    """Run a command and return the result."""
    if not args:
        raise ValueError("Empty command")
    executable = args[0]
    if executable not in _ALLOWED_EXECUTABLES:
        raise ValueError(f"Executable not in allowlist: {executable}")
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding=encoding,
        check=True,
        shell=False,
    )


@lru_cache(maxsize=1)
def detect_cuda_version() -> Version | None:
    """
    Detect CUDA version from nvidia-smi output.

    Returns:
        Version object with major/minor version, or None if not found
    """
    try:
        result = _run_cmd(['nvidia-smi'])
        output = result.stdout.strip()

        # Look for CUDA Version in the output
        cuda_match = re.search(r'CUDA Version\s*:\s*(\d+)\.(\d+)', output)
        if cuda_match:
            return Version(int(cuda_match.group(1)), int(cuda_match.group(2)))
    except (OSError, subprocess.CalledProcessError, FileNotFoundError):
        pass

    return None


@lru_cache(maxsize=1)
def detect_rocm_version() -> Version | None:
    """
    Detect ROCm version from rocm-smi, rocminfo, or version file.

    Returns:
        Version object with major/minor/patch version, or None if not found
    """
    # Try rocm-smi first
    try:
        result = _run_cmd(['rocm-smi', '--showversion'])
        output = result.stdout.strip()
        # Parse output like "ROCm SMI version: 6.3.0"
        match = re.search(r'ROCm.*version[:\s]+(\d+)\.(\d+)(?:\.(\d+))?', output, re.IGNORECASE)
        if match:
            return Version(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)) if match.group(3) else 0
            )
    except (OSError, subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Fallback to rocminfo
    try:
        result = _run_cmd(['rocminfo'])
        output = result.stdout.strip()
        # Parse output for ROCm version
        match = re.search(r'ROCm.*Runtime Version[:\s]+(\d+)\.(\d+)(?:\.(\d+))?', output, re.IGNORECASE)
        if match:
            return Version(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)) if match.group(3) else 0
            )
    except (OSError, subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Check /opt/rocm/.info/version file
    try:
        version_file = Path("/opt/rocm/.info/version")
        if version_file.exists():
            content = version_file.read_text().strip()
            # Version format might be "6.3.0" or "6.3.0-12345"
            parts = content.split("-")[0].split(".")
            return Version(
                int(parts[0]),
                int(parts[1]) if len(parts) > 1 else 0,
                int(parts[2]) if len(parts) > 2 else 0
            )
    except (OSError, ValueError):
        pass

    return None


def _count_nvidia_gpus() -> int:
    """Count NVIDIA GPUs using nvidia-smi."""
    try:
        result = _run_cmd(['nvidia-smi', '--query-gpu=index', '--format=csv,noheader'])
        output = result.stdout.strip()
        return len(output.splitlines()) if output else 0
    except (OSError, subprocess.CalledProcessError, FileNotFoundError):
        return 0


def _detect_nvidia() -> GpuInfo | None:
    """Detect NVIDIA GPU and CUDA version."""
    cuda_version = detect_cuda_version()
    if cuda_version:
        return GpuInfo(
            gpu_type="cuda",
            driver_version=cuda_version,
            device_count=_count_nvidia_gpus(),
        )
    return None


def _detect_amd_gpus() -> tuple[int, int, int]:
    """
    Detect AMD GPUs using KFD sysfs interface.

    Returns:
        Tuple of (count, total_memory_bytes, best_gfx_version)
    """
    count = 0
    total_memory = 0
    best_gfx_version = 0

    try:
        for _, props in amdkfd.gpus():
            gfx_version = props.get('gfx_target_version', 0)
            # Radeon GPUs older than gfx900 are not supported by ROCm
            if gfx_version < 90000:
                continue

            count += 1
            if gfx_version > best_gfx_version:
                best_gfx_version = gfx_version

            # Calculate VRAM from memory banks
            mem_banks_count = int(props.get('mem_banks_count', 0))
            for bank in range(mem_banks_count):
                try:
                    node_path = f'/sys/devices/virtual/kfd/kfd/topology/nodes/{props.get("node_id", 0)}'
                    bank_props = amdkfd.parse_props(f'{node_path}/mem_banks/{bank}/properties')
                    # Count public and private framebuffer memory as VRAM
                    if bank_props.get('heap_type', 0) in [amdkfd.HEAP_TYPE_FB_PUBLIC, amdkfd.HEAP_TYPE_FB_PRIVATE]:
                        total_memory += int(bank_props.get('size_in_bytes', 0))
                except (OSError, KeyError, ValueError):
                    pass
    except (OSError, KeyError, ValueError):
        pass

    return count, total_memory, best_gfx_version


def _detect_amd() -> GpuInfo | None:
    """Detect AMD GPU with ROCm support."""
    if is_arm():
        return None

    count, memory, gfx_version = _detect_amd_gpus()
    if count > 0:
        rocm_version = detect_rocm_version()
        if rocm_version is None:
            return None
        return GpuInfo(
            gpu_type="hip",
            driver_version=rocm_version,
            device_count=count,
            memory_bytes=memory,
            gfx_version=gfx_version,
        )
    return None


def _detect_intel_gpus() -> int:
    """Detect Intel GPUs using PCI sysfs interface."""
    # Device IDs for select Intel GPUs
    # See: https://dgpu-docs.intel.com/devices/hardware-table.html
    intel_gpus = (
        b"0xe20b",  # Arc A770
        b"0xe20c",  # Arc A750
        b"0x46a6",
        b"0x46a8",
        b"0x46aa",
        b"0x56a0",
        b"0x56a1",
        b"0x7d51",
        b"0x7dd5",
        b"0x7d55",
    )
    intel_driver_patterns = [
        "/sys/bus/pci/drivers/i915/*/device",
        "/sys/bus/pci/drivers/xe/*/device"
    ]

    count = 0
    for fp in sorted([i for p in intel_driver_patterns for i in glob.glob(p)]):
        try:
            with open(fp, 'rb') as file:
                content = file.read()
                if any(gpu_id in content for gpu_id in intel_gpus):
                    count += 1
        except OSError:
            pass

    return count


def _detect_intel() -> GpuInfo | None:
    """Detect Intel GPU."""
    count = _detect_intel_gpus()
    if count > 0:
        return GpuInfo(
            gpu_type="intel",
            device_count=count,
        )
    return None


def _detect_asahi() -> GpuInfo | None:
    """Detect Asahi Linux (Apple Silicon on Linux)."""
    try:
        with open('/proc/device-tree/compatible', 'rb') as f:
            content = f.read().split(b"\0")
            if b"apple,arm-platform" in content:
                return GpuInfo(gpu_type="asahi", device_count=1)
    except OSError:
        pass
    return None


def _detect_metal() -> GpuInfo | None:
    """Detect macOS Metal GPU support."""
    if platform.system() == "Darwin":
        return GpuInfo(gpu_type="metal", device_count=1)
    return None


def _detect_ascend() -> GpuInfo | None:
    """Detect Huawei Ascend NPU."""
    try:
        _run_cmd(['npu-smi', 'info'])
        return GpuInfo(gpu_type="cann", device_count=1)
    except (OSError, subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None


def _detect_mthreads() -> GpuInfo | None:
    """Detect Mthreads GPU (MUSA)."""
    try:
        _run_cmd(['mthreads-gmi'])
        return GpuInfo(gpu_type="musa", device_count=1)
    except (OSError, subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None


@lru_cache(maxsize=1)
def detect_gpu() -> GpuInfo:
    """
    Detect GPU hardware and driver version.

    Checks GPUs in priority order:
    1. Asahi (Apple Silicon on Linux)
    2. NVIDIA CUDA
    3. Huawei Ascend (CANN)
    4. AMD ROCm (HIP)
    5. Intel GPU
    6. Mthreads (MUSA)
    7. Metal (macOS)

    Returns:
        GpuInfo with detected GPU details, or GpuInfo(gpu_type="none") if no GPU found
    """
    # Check in priority order (same as get_accel() in common.py)
    detectors = [
        _detect_asahi,
        _detect_nvidia,
        _detect_ascend,
        _detect_amd,
        _detect_intel,
        _detect_mthreads,
        _detect_metal,
    ]

    for detector in detectors:
        result = detector()
        if result:
            return result

    return GpuInfo(gpu_type="none")


def detect_hardware_profile(is_container: bool = False) -> HardwareProfile:
    """
    Detect complete hardware profile for the current system.

    Args:
        is_container: Whether running inside a container

    Returns:
        HardwareProfile with architecture, GPU info, OS type, and container flag
    """
    return HardwareProfile(
        architecture=get_architecture(),
        gpu=detect_gpu(),
        is_container=is_container,
        os_type=get_os_type(),
    )


def clear_detection_cache():
    """Clear all cached detection results (useful for testing)."""
    detect_cuda_version.cache_clear()
    detect_rocm_version.cache_clear()
    detect_gpu.cache_clear()
