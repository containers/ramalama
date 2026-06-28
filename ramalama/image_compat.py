"""Compatibility matrix schema and loading for automated image selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ramalama.hardware import Architecture, GpuType, HardwareProfile, OsType
from ramalama.version_constraints import VersionRange


def _image_has_tag_or_digest(image: str) -> bool:
    """
    Check if an image reference already has a tag or digest.

    Handles registry URLs with ports (e.g., localhost:5000/repo/image).
    """
    if "@" in image:
        return True
    last_segment = image.split("/")[-1]
    return ":" in last_segment


@dataclass
class ImageConstraints:
    """
    Constraints that must be satisfied for an image to be compatible.

    All constraint lists use AND logic within a category and OR logic between items.
    For example, architectures=["x86_64", "aarch64"] means the image supports
    EITHER x86_64 OR aarch64.
    """

    architectures: list[Architecture] = field(default_factory=lambda: ["x86_64", "aarch64"])
    gpu_types: list[GpuType] = field(default_factory=lambda: ["none"])
    driver_version: VersionRange = field(default_factory=lambda: VersionRange.from_string("*"))
    runtimes: list[str] = field(default_factory=lambda: ["llama.cpp"])
    os_types: list[OsType] = field(default_factory=lambda: ["linux"])

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImageConstraints":
        """
        Create ImageConstraints from a dictionary.

        Args:
            data: Dictionary with constraint fields

        Returns:
            ImageConstraints object
        """
        return cls(
            architectures=data.get("architectures", ["x86_64", "aarch64"]),
            gpu_types=data.get("gpu_types", ["none"]),
            driver_version=VersionRange.from_string(data.get("driver_version", "*")),
            runtimes=data.get("runtimes", ["llama.cpp"]),
            os_types=data.get("os_types", ["linux"]),
        )

    def matches(self, profile: HardwareProfile, runtime: str) -> bool:
        """
        Check if this constraint set matches the hardware profile.

        Args:
            profile: Hardware profile to check
            runtime: Runtime being used (e.g., "llama.cpp", "vllm", "mlx")

        Returns:
            True if all constraints are satisfied
        """
        if profile.architecture not in self.architectures:
            return False
        if profile.gpu.gpu_type not in self.gpu_types:
            return False
        if not self.driver_version.matches(profile.gpu.driver_version):
            return False
        if runtime not in self.runtimes:
            return False
        if profile.os_type not in self.os_types:
            return False
        return True


@dataclass
class ImageEntry:
    """
    A single image entry in the compatibility matrix.

    Attributes:
        image: The container image URL (e.g., "quay.io/ramalama/cuda")
        constraints: Hardware and runtime constraints for this image
        priority: Higher priority images are preferred when multiple match (default 0)
        tags: Version-specific tags mapping driver version to image tag
    """

    image: str
    constraints: ImageConstraints
    priority: int = 0
    tags: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImageEntry":
        """
        Create ImageEntry from a dictionary.

        Args:
            data: Dictionary with image and constraints

        Returns:
            ImageEntry object
        """
        return cls(
            image=data["image"],
            constraints=ImageConstraints.from_dict(data.get("constraints", {})),
            priority=data.get("priority", 0),
            tags=data.get("tags", {}),
        )


@dataclass
class ImageCompatibilityMatrix:
    """
    Complete compatibility matrix for image selection.

    The matrix contains a list of image entries with their constraints,
    and provides methods to select the best matching image for a given
    hardware profile and runtime.
    """

    schema_version: str
    default_image: str
    entries: list[ImageEntry]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImageCompatibilityMatrix":
        """
        Create ImageCompatibilityMatrix from a dictionary.

        Args:
            data: Dictionary with schema_version, default_image, and images list

        Returns:
            ImageCompatibilityMatrix object
        """
        return cls(
            schema_version=data.get("schema_version", "1.0.0"),
            default_image=data.get("default_image", "quay.io/ramalama/ramalama"),
            entries=[ImageEntry.from_dict(e) for e in data.get("images", [])],
        )

    @classmethod
    def load(cls, path: Path) -> "ImageCompatibilityMatrix":
        """
        Load compatibility matrix from YAML file.

        Args:
            path: Path to YAML file

        Returns:
            ImageCompatibilityMatrix object

        Raises:
            FileNotFoundError: If file doesn't exist
            yaml.YAMLError: If YAML is invalid
            ValueError: If YAML content is not a mapping
        """
        with open(path) as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(
                f"Expected top-level mapping in {path}, got {type(data).__name__}"
            )
        return cls.from_dict(data)

    def select_image(
        self,
        profile: HardwareProfile,
        runtime: str,
        fallback: str | None = None,
    ) -> str:
        """
        Select the best matching image for the given hardware profile and runtime.

        Args:
            profile: Hardware profile to match against
            runtime: Runtime being used (e.g., "llama.cpp", "vllm")
            fallback: Fallback image if no match found (defaults to default_image)

        Returns:
            The best matching image URL
        """
        matching = [
            entry for entry in self.entries
            if entry.constraints.matches(profile, runtime)
        ]

        if not matching:
            return fallback or self.default_image

        # Sort by priority (descending) and return highest priority match
        matching.sort(key=lambda e: e.priority, reverse=True)
        return matching[0].image

    def select_image_with_tag(
        self,
        profile: HardwareProfile,
        runtime: str,
        default_tag: str = "latest",
        fallback: str | None = None,
    ) -> str:
        """
        Select image with version-specific tag if available.

        This method first selects the best matching image, then checks if
        there's a version-specific tag based on the GPU driver version.

        Args:
            profile: Hardware profile to match against
            runtime: Runtime being used
            default_tag: Default tag to use if no version-specific tag found
            fallback: Fallback image if no match found

        Returns:
            The image URL with appropriate tag (e.g., "quay.io/ramalama/cuda:0.17-12.4.1")
        """
        matching = [
            entry for entry in self.entries
            if entry.constraints.matches(profile, runtime)
        ]

        if not matching:
            image = fallback or self.default_image
            if _image_has_tag_or_digest(image):
                return image
            return f"{image}:{default_tag}"

        matching.sort(key=lambda e: e.priority, reverse=True)
        best = matching[0]
        image = best.image

        if _image_has_tag_or_digest(image):
            return image

        # Check for version-specific tags based on driver version
        if profile.gpu.driver_version and best.tags:
            version = profile.gpu.driver_version
            # Try exact major.minor match first
            version_key = f"{version.major}.{version.minor}"
            if version_key in best.tags:
                tag = best.tags[version_key]
                return f"{image}:{tag}"

            # Try major version only
            major_key = str(version.major)
            if major_key in best.tags:
                tag = best.tags[major_key]
                return f"{image}:{tag}"

        return f"{image}:{default_tag}"

    def get_matching_entries(
        self,
        profile: HardwareProfile,
        runtime: str,
    ) -> list[ImageEntry]:
        """
        Get all entries matching the hardware profile and runtime.

        Args:
            profile: Hardware profile to match
            runtime: Runtime being used

        Returns:
            List of matching entries sorted by priority (highest first)
        """
        matching = [
            entry for entry in self.entries
            if entry.constraints.matches(profile, runtime)
        ]
        matching.sort(key=lambda e: e.priority, reverse=True)
        return matching


def create_default_matrix() -> ImageCompatibilityMatrix:
    """
    Create a default compatibility matrix matching existing RamalamaImages behavior.

    This is used as a fallback when no images.yaml file is found.

    Returns:
        ImageCompatibilityMatrix with default image entries
    """
    return ImageCompatibilityMatrix(
        schema_version="1.0.0",
        default_image="quay.io/ramalama/ramalama",
        entries=[
            # CUDA images
            ImageEntry(
                image="quay.io/ramalama/cuda",
                priority=100,
                constraints=ImageConstraints(
                    architectures=["x86_64"],
                    gpu_types=["cuda"],
                    driver_version=VersionRange.from_string(">=12.4"),
                    runtimes=["llama.cpp"],
                    os_types=["linux", "windows"],
                ),
            ),
            # ROCm images
            ImageEntry(
                image="quay.io/ramalama/rocm",
                priority=100,
                constraints=ImageConstraints(
                    architectures=["x86_64"],
                    gpu_types=["hip"],
                    driver_version=VersionRange.from_string(">=5.0"),
                    runtimes=["llama.cpp"],
                    os_types=["linux"],
                ),
            ),
            # Intel GPU images
            ImageEntry(
                image="quay.io/ramalama/intel-gpu",
                priority=100,
                constraints=ImageConstraints(
                    architectures=["x86_64"],
                    gpu_types=["intel"],
                    runtimes=["llama.cpp"],
                    os_types=["linux"],
                ),
            ),
            # Asahi images
            ImageEntry(
                image="quay.io/ramalama/asahi",
                priority=100,
                constraints=ImageConstraints(
                    architectures=["aarch64"],
                    gpu_types=["asahi"],
                    runtimes=["llama.cpp"],
                    os_types=["linux"],
                ),
            ),
            # CANN (Ascend) images
            ImageEntry(
                image="quay.io/ramalama/cann",
                priority=100,
                constraints=ImageConstraints(
                    architectures=["x86_64", "aarch64"],
                    gpu_types=["cann"],
                    runtimes=["llama.cpp"],
                    os_types=["linux"],
                ),
            ),
            # MUSA (Mthreads) images
            ImageEntry(
                image="quay.io/ramalama/musa",
                priority=100,
                constraints=ImageConstraints(
                    architectures=["x86_64"],
                    gpu_types=["musa"],
                    runtimes=["llama.cpp"],
                    os_types=["linux"],
                ),
            ),
            # vLLM CUDA images
            ImageEntry(
                image="docker.io/vllm/vllm-openai",
                priority=50,
                constraints=ImageConstraints(
                    architectures=["x86_64"],
                    gpu_types=["cuda"],
                    driver_version=VersionRange.from_string(">=12.0"),
                    runtimes=["vllm"],
                    os_types=["linux"],
                ),
            ),
            # vLLM ROCm images
            ImageEntry(
                image="docker.io/vllm/vllm-openai",
                priority=50,
                constraints=ImageConstraints(
                    architectures=["x86_64"],
                    gpu_types=["hip"],
                    driver_version=VersionRange.from_string(">=5.0"),
                    runtimes=["vllm"],
                    os_types=["linux"],
                ),
            ),
            # Default CPU/Vulkan fallback
            ImageEntry(
                image="quay.io/ramalama/ramalama",
                priority=1,
                constraints=ImageConstraints(
                    architectures=["x86_64", "aarch64"],
                    gpu_types=["none", "vulkan"],
                    runtimes=["llama.cpp"],
                    os_types=["linux", "darwin", "windows"],
                ),
            ),
        ],
    )
