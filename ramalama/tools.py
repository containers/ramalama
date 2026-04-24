"""Tools container image selection for GGUF conversion."""

from ramalama.common import accel_image, version_tagged_image
from ramalama.config import Config

_DEFAULT_TOOLS_IMAGES: dict[str, str] = {
    "CUDA_VISIBLE_DEVICES": version_tagged_image("quay.io/ramalama/cuda-tools"),
    "HIP_VISIBLE_DEVICES": version_tagged_image("quay.io/ramalama/rocm-tools"),
    "INTEL_VISIBLE_DEVICES": version_tagged_image("quay.io/ramalama/intel-gpu-tools"),
}

DEFAULT_TOOLS_IMAGE: str = version_tagged_image("quay.io/ramalama/ramalama-tools")


def tools_image(config: Config) -> str:
    images = _DEFAULT_TOOLS_IMAGES | config.tools_images
    return accel_image(config, images=images, conf_key="tools_image")
