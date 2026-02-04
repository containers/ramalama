"""Unit tests for image_compat module."""

import tempfile
from pathlib import Path

import pytest

from ramalama.hardware import GpuInfo, HardwareProfile
from ramalama.image_compat import (
    ImageCompatibilityMatrix,
    ImageConstraints,
    ImageEntry,
    create_default_matrix,
)
from ramalama.version_constraints import Version, VersionRange


class TestImageConstraints:
    """Tests for ImageConstraints class."""

    def test_default_constraints(self):
        constraints = ImageConstraints()
        assert "x86_64" in constraints.architectures
        assert "aarch64" in constraints.architectures
        assert "none" in constraints.gpu_types
        assert "llama.cpp" in constraints.runtimes
        assert "linux" in constraints.os_types

    def test_from_dict(self):
        data = {
            "architectures": ["x86_64"],
            "gpu_types": ["cuda"],
            "driver_version": ">=12.4",
            "runtimes": ["llama.cpp", "vllm"],
            "os_types": ["linux"],
        }
        constraints = ImageConstraints.from_dict(data)
        assert constraints.architectures == ["x86_64"]
        assert constraints.gpu_types == ["cuda"]
        assert constraints.runtimes == ["llama.cpp", "vllm"]

    @pytest.mark.parametrize(
        "arch,gpu_type,driver_version,runtime,os_type,expected",
        [
            # Matching cases
            ("x86_64", "cuda", "12.8.0", "llama.cpp", "linux", True),
            ("x86_64", "cuda", "12.4.0", "llama.cpp", "linux", True),
            # Non-matching cases
            ("aarch64", "cuda", "12.8.0", "llama.cpp", "linux", False),  # wrong arch
            ("x86_64", "hip", "6.3.0", "llama.cpp", "linux", False),  # wrong GPU
            ("x86_64", "cuda", "11.0.0", "llama.cpp", "linux", False),  # version too old
            ("x86_64", "cuda", "12.8.0", "mlx", "linux", False),  # wrong runtime
            ("x86_64", "cuda", "12.8.0", "llama.cpp", "darwin", False),  # wrong OS
        ],
    )
    def test_matches(self, arch, gpu_type, driver_version, runtime, os_type, expected):
        constraints = ImageConstraints(
            architectures=["x86_64"],
            gpu_types=["cuda"],
            driver_version=VersionRange.from_string(">=12.4"),
            runtimes=["llama.cpp"],
            os_types=["linux"],
        )
        profile = HardwareProfile(
            architecture=arch,
            gpu=GpuInfo(gpu_type=gpu_type, driver_version=Version.from_string(driver_version)),
            os_type=os_type,
        )
        assert constraints.matches(profile, runtime) == expected

    def test_matches_wildcard_version(self):
        constraints = ImageConstraints(
            architectures=["x86_64"],
            gpu_types=["hip"],
            driver_version=VersionRange.from_string("*"),
            runtimes=["llama.cpp"],
            os_types=["linux"],
        )
        profile = HardwareProfile(
            architecture="x86_64",
            gpu=GpuInfo(gpu_type="hip"),  # No driver version
            os_type="linux",
        )
        assert constraints.matches(profile, "llama.cpp") is True


class TestImageEntry:
    """Tests for ImageEntry class."""

    def test_from_dict_minimal(self):
        data = {"image": "quay.io/ramalama/cuda"}
        entry = ImageEntry.from_dict(data)
        assert entry.image == "quay.io/ramalama/cuda"
        assert entry.priority == 0
        assert entry.tags == {}

    def test_from_dict_full(self):
        data = {
            "image": "quay.io/ramalama/cuda",
            "priority": 100,
            "constraints": {
                "architectures": ["x86_64"],
                "gpu_types": ["cuda"],
            },
            "tags": {"12.4": "latest-12.4.1"},
        }
        entry = ImageEntry.from_dict(data)
        assert entry.image == "quay.io/ramalama/cuda"
        assert entry.priority == 100
        assert entry.tags == {"12.4": "latest-12.4.1"}
        assert entry.constraints.architectures == ["x86_64"]


class TestImageCompatibilityMatrix:
    """Tests for ImageCompatibilityMatrix class."""

    def test_from_dict(self):
        data = {
            "schema_version": "1.0.0",
            "default_image": "quay.io/ramalama/ramalama",
            "images": [
                {
                    "image": "quay.io/ramalama/cuda",
                    "priority": 100,
                    "constraints": {"gpu_types": ["cuda"]},
                }
            ],
        }
        matrix = ImageCompatibilityMatrix.from_dict(data)
        assert matrix.schema_version == "1.0.0"
        assert matrix.default_image == "quay.io/ramalama/ramalama"
        assert len(matrix.entries) == 1

    def test_select_image_matching(self):
        matrix = ImageCompatibilityMatrix(
            schema_version="1.0.0",
            default_image="quay.io/ramalama/ramalama",
            entries=[
                ImageEntry(
                    image="quay.io/ramalama/cuda",
                    constraints=ImageConstraints(gpu_types=["cuda"]),
                    priority=100,
                ),
                ImageEntry(
                    image="quay.io/ramalama/rocm",
                    constraints=ImageConstraints(gpu_types=["hip"]),
                    priority=100,
                ),
            ],
        )

        # Test CUDA selection
        cuda_profile = HardwareProfile(
            architecture="x86_64",
            gpu=GpuInfo(gpu_type="cuda"),
            os_type="linux",
        )
        assert matrix.select_image(cuda_profile, "llama.cpp") == "quay.io/ramalama/cuda"

        # Test ROCm selection
        rocm_profile = HardwareProfile(
            architecture="x86_64",
            gpu=GpuInfo(gpu_type="hip"),
            os_type="linux",
        )
        assert matrix.select_image(rocm_profile, "llama.cpp") == "quay.io/ramalama/rocm"

    def test_select_image_fallback(self):
        matrix = ImageCompatibilityMatrix(
            schema_version="1.0.0",
            default_image="quay.io/ramalama/ramalama",
            entries=[],
        )
        profile = HardwareProfile(
            architecture="x86_64",
            gpu=GpuInfo(gpu_type="none"),
            os_type="linux",
        )
        assert matrix.select_image(profile, "llama.cpp") == "quay.io/ramalama/ramalama"

    def test_select_image_priority(self):
        matrix = ImageCompatibilityMatrix(
            schema_version="1.0.0",
            default_image="quay.io/ramalama/ramalama",
            entries=[
                ImageEntry(
                    image="quay.io/ramalama/cuda-low",
                    constraints=ImageConstraints(gpu_types=["cuda"]),
                    priority=10,
                ),
                ImageEntry(
                    image="quay.io/ramalama/cuda-high",
                    constraints=ImageConstraints(gpu_types=["cuda"]),
                    priority=100,
                ),
            ],
        )
        profile = HardwareProfile(
            architecture="x86_64",
            gpu=GpuInfo(gpu_type="cuda"),
            os_type="linux",
        )
        # Higher priority should win
        assert matrix.select_image(profile, "llama.cpp") == "quay.io/ramalama/cuda-high"

    def test_select_image_with_tag_version_specific(self):
        matrix = ImageCompatibilityMatrix(
            schema_version="1.0.0",
            default_image="quay.io/ramalama/ramalama",
            entries=[
                ImageEntry(
                    image="quay.io/ramalama/cuda",
                    constraints=ImageConstraints(gpu_types=["cuda"]),
                    priority=100,
                    tags={"12.4": "latest-12.4.1", "12.5": "latest-12.4.1"},
                ),
            ],
        )
        profile = HardwareProfile(
            architecture="x86_64",
            gpu=GpuInfo(gpu_type="cuda", driver_version=Version(12, 4, 0)),
            os_type="linux",
        )
        result = matrix.select_image_with_tag(profile, "llama.cpp", default_tag="latest")
        assert result == "quay.io/ramalama/cuda:latest-12.4.1"

    def test_select_image_with_tag_default(self):
        matrix = ImageCompatibilityMatrix(
            schema_version="1.0.0",
            default_image="quay.io/ramalama/ramalama",
            entries=[
                ImageEntry(
                    image="quay.io/ramalama/cuda",
                    constraints=ImageConstraints(gpu_types=["cuda"]),
                    priority=100,
                    tags={},  # No version-specific tags
                ),
            ],
        )
        profile = HardwareProfile(
            architecture="x86_64",
            gpu=GpuInfo(gpu_type="cuda", driver_version=Version(12, 8, 0)),
            os_type="linux",
        )
        result = matrix.select_image_with_tag(profile, "llama.cpp", default_tag="0.17")
        assert result == "quay.io/ramalama/cuda:0.17"

    def test_load_from_yaml(self):
        yaml_content = """
schema_version: "1.0.0"
default_image: "quay.io/ramalama/ramalama"
images:
  - image: "quay.io/ramalama/cuda"
    priority: 100
    constraints:
      architectures: ["x86_64"]
      gpu_types: ["cuda"]
      driver_version: ">=12.4"
      runtimes: ["llama.cpp"]
      os_types: ["linux"]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            matrix = ImageCompatibilityMatrix.load(Path(f.name))
            assert matrix.schema_version == "1.0.0"
            assert len(matrix.entries) == 1
            assert matrix.entries[0].image == "quay.io/ramalama/cuda"


class TestDefaultMatrix:
    """Tests for the default compatibility matrix."""

    def test_create_default_matrix(self):
        matrix = create_default_matrix()
        assert matrix.default_image == "quay.io/ramalama/ramalama"
        assert len(matrix.entries) > 0

        # Check that CUDA entry exists
        cuda_entries = [e for e in matrix.entries if "cuda" in e.image and "rag" not in e.image]
        assert len(cuda_entries) >= 1

        # Check that ROCm entry exists
        rocm_entries = [e for e in matrix.entries if "rocm" in e.image and "rag" not in e.image]
        assert len(rocm_entries) >= 1

    def test_default_matrix_cuda_selection(self):
        matrix = create_default_matrix()
        profile = HardwareProfile(
            architecture="x86_64",
            gpu=GpuInfo(gpu_type="cuda", driver_version=Version(12, 8, 0)),
            os_type="linux",
        )
        result = matrix.select_image(profile, "llama.cpp")
        assert "cuda" in result

    def test_default_matrix_fallback(self):
        matrix = create_default_matrix()
        profile = HardwareProfile(
            architecture="x86_64",
            gpu=GpuInfo(gpu_type="none"),
            os_type="linux",
        )
        result = matrix.select_image(profile, "llama.cpp")
        assert result == "quay.io/ramalama/ramalama"
