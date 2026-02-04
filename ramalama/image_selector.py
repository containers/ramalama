"""Image selection based on hardware detection and compatibility matrix."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from ramalama.config import DEFAULT_IMAGE, get_image_matrix_files
from ramalama.hardware import HardwareProfile, detect_hardware_profile
from ramalama.image_compat import ImageCompatibilityMatrix, create_default_matrix

if TYPE_CHECKING:
    from ramalama.config import Config


@lru_cache(maxsize=1)
def load_image_matrix() -> ImageCompatibilityMatrix:
    """
    Load the image compatibility matrix from available config files.

    Searches for images.yaml in:
    1. inference-spec/images/ (development)
    2. /etc/ramalama/inference/images/ (system)
    3. ~/.config/ramalama/inference/images/ (user)

    User config takes precedence over system config.

    Returns:
        ImageCompatibilityMatrix loaded from file, or default matrix if no file found
    """
    paths = get_image_matrix_files()
    if not paths:
        # Return default matrix if no file found
        return create_default_matrix()

    # Load from last available path (user config takes precedence)
    return ImageCompatibilityMatrix.load(paths[-1])


def select_image(
    config: Config,
    runtime: str = "llama.cpp",
    is_container: bool = True,
    is_rag: bool = False,
) -> str:
    """
    Select the appropriate container image based on hardware detection and compatibility matrix.

    This function performs automatic hardware detection to determine the best
    container image for the current system. It considers:
    - CPU architecture (x86_64 vs aarch64)
    - GPU type (CUDA, ROCm, Intel, etc.)
    - GPU driver version (e.g., CUDA 12.4 vs 12.8)
    - Runtime (llama.cpp, vllm, mlx)

    Args:
        config: RamaLama configuration object
        runtime: The inference runtime being used (llama.cpp, vllm, mlx)
        is_container: Whether running in container mode
        is_rag: Whether this is a RAG operation (uses different images)

    Returns:
        The fully qualified image name with tag (e.g., "quay.io/ramalama/cuda:0.17")
    """
    # Import here to avoid circular imports
    from ramalama.common import minor_release

    # Determine the config key and default image based on RAG mode
    if is_rag:
        conf_key = "rag_image"
        default_image = config.default_rag_image
    else:
        conf_key = "image"
        default_image = config.default_image

    # Check if user has explicitly set an image
    if config.is_set(conf_key):
        image = getattr(config, conf_key)
        return _tag_image(image, minor_release())

    # Detect hardware profile
    profile = detect_hardware_profile(is_container)

    # Adjust runtime for RAG mode
    effective_runtime = f"{runtime}-rag" if is_rag else runtime

    # Load compatibility matrix and select image
    matrix = load_image_matrix()
    image = matrix.select_image_with_tag(
        profile=profile,
        runtime=effective_runtime,
        default_tag=minor_release(),
        fallback=default_image,
    )

    return image


def select_image_for_gpu(
    config: Config,
    runtime: str = "llama.cpp",
    is_rag: bool = False,
) -> str:
    """
    Select image based on detected GPU type, with backward compatibility.

    This function provides backward compatibility with the existing
    accel_image() behavior while using the new compatibility matrix.

    Args:
        config: RamaLama configuration object
        runtime: The inference runtime being used
        is_rag: Whether this is a RAG operation

    Returns:
        The selected image URL with tag
    """
    return select_image(config, runtime=runtime, is_container=True, is_rag=is_rag)


def _tag_image(image: str, default_tag: str) -> str:
    """
    Add version tag to image if not already tagged.

    Args:
        image: Image URL (may or may not have tag)
        default_tag: Tag to use if image is untagged

    Returns:
        Image URL with tag
    """
    # Already has tag (colon in name) or digest (@ symbol)
    if ":" in image or "@" in image:
        return image
    return f"{image}:{default_tag}"


def get_hardware_summary() -> dict[str, str]:
    """
    Get a human-readable summary of detected hardware.

    Useful for debugging and logging.

    Returns:
        Dictionary with hardware information
    """
    profile = detect_hardware_profile()
    gpu = profile.gpu

    summary = {
        "architecture": profile.architecture,
        "os_type": profile.os_type,
        "gpu_type": gpu.gpu_type,
        "gpu_device_count": str(gpu.device_count),
    }

    if gpu.driver_version:
        summary["gpu_driver_version"] = str(gpu.driver_version)

    if gpu.memory_bytes:
        summary["gpu_memory_gb"] = f"{gpu.memory_bytes / (1024**3):.1f}"

    if gpu.gfx_version:
        summary["gpu_gfx_version"] = str(gpu.gfx_version)

    return summary


def clear_image_cache():
    """Clear cached image matrix (useful for testing or config changes)."""
    load_image_matrix.cache_clear()
