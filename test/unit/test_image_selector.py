"""Unit tests for image_selector module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ramalama.hardware import GpuInfo, HardwareProfile
from ramalama.image_compat import (
    ImageCompatibilityMatrix,
    ImageConstraints,
    ImageEntry,
)
from ramalama.image_selector import (
    _tag_image,
    clear_image_cache,
    get_hardware_summary,
    image_has_tag_or_digest,
    load_image_matrix,
    select_image,
)
from ramalama.version_constraints import Version


class TestImageHasTagOrDigest:
    """Tests for image_has_tag_or_digest helper function."""

    def test_registry_with_port_untagged(self):
        assert image_has_tag_or_digest("localhost:5000/ramalama/cuda") is False

    def test_registry_with_port_tagged(self):
        assert image_has_tag_or_digest("localhost:5000/ramalama/cuda:latest") is True

    def test_simple_tagged(self):
        assert image_has_tag_or_digest("quay.io/ramalama/cuda:pretagged") is True

    def test_simple_untagged(self):
        assert image_has_tag_or_digest("quay.io/ramalama/cuda") is False

    def test_digest(self):
        assert image_has_tag_or_digest("quay.io/ramalama/cuda@sha256:deadbeef") is True

    def test_registry_port_with_digest(self):
        assert image_has_tag_or_digest("localhost:5000/repo@sha256:abc123") is True


class TestTagImage:
    """Tests for _tag_image helper function."""

    def test_already_tagged(self):
        assert _tag_image("quay.io/ramalama/cuda:1.0", "latest") == "quay.io/ramalama/cuda:1.0"

    def test_with_digest(self):
        result = _tag_image("quay.io/ramalama/cuda@sha256:abc", "latest")
        assert result == "quay.io/ramalama/cuda@sha256:abc"

    def test_untagged(self):
        assert _tag_image("quay.io/ramalama/cuda", "0.17") == "quay.io/ramalama/cuda:0.17"

    def test_registry_with_port_gets_tagged(self):
        result = _tag_image("localhost:5000/ramalama/cuda", "0.17")
        assert result == "localhost:5000/ramalama/cuda:0.17"

    def test_registry_with_port_pretagged_unchanged(self):
        result = _tag_image("localhost:5000/ramalama/cuda:pretagged", "0.17")
        assert result == "localhost:5000/ramalama/cuda:pretagged"


class TestLoadImageMatrix:
    """Tests for load_image_matrix function."""

    def setup_method(self):
        clear_image_cache()

    @patch("ramalama.image_selector.get_image_matrix_files")
    def test_no_files_returns_default(self, mock_get_files):
        mock_get_files.return_value = []
        matrix = load_image_matrix()
        assert matrix.default_image == "quay.io/ramalama/ramalama"
        assert len(matrix.entries) > 0

    @patch("ramalama.image_selector.get_image_matrix_files")
    def test_precedence_last_wins(self, mock_get_files):
        yaml1 = """
schema_version: "1.0.0"
default_image: "first/image"
images: []
"""
        yaml2 = """
schema_version: "1.0.0"
default_image: "second/image"
images: []
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f1:
            f1.write(yaml1)
            f1.flush()
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f2:
                f2.write(yaml2)
                f2.flush()
                mock_get_files.return_value = [Path(f1.name), Path(f2.name)]
                clear_image_cache()
                matrix = load_image_matrix()
                assert matrix.default_image == "second/image"

    @patch("ramalama.image_selector.get_image_matrix_files")
    def test_caching_behavior(self, mock_get_files):
        yaml_content = """
schema_version: "1.0.0"
default_image: "cached/image"
images: []
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            mock_get_files.return_value = [Path(f.name)]
            clear_image_cache()
            load_image_matrix()
            load_image_matrix()
            assert mock_get_files.call_count == 1
            clear_image_cache()
            load_image_matrix()
            assert mock_get_files.call_count == 2


class TestSelectImage:
    """Tests for select_image function."""

    def setup_method(self):
        clear_image_cache()

    @patch("ramalama.image_selector.detect_hardware_profile")
    @patch("ramalama.image_selector.load_image_matrix")
    @patch("ramalama.common.minor_release")
    def test_user_config_override(self, mock_release, mock_matrix, mock_profile):
        """User-specified image should be used directly."""
        mock_release.return_value = "0.17"
        config = MagicMock()
        config.is_set.return_value = True
        config.image = "my-custom-image"

        result = select_image(config)
        assert result == "my-custom-image:0.17"
        mock_profile.assert_not_called()

    @patch("ramalama.image_selector.detect_hardware_profile")
    @patch("ramalama.image_selector.load_image_matrix")
    @patch("ramalama.common.minor_release")
    def test_cuda_selection(self, mock_release, mock_matrix, mock_profile):
        """CUDA GPU should select CUDA image."""
        mock_release.return_value = "0.17"
        config = MagicMock()
        config.is_set.return_value = False
        config.default_image = "quay.io/ramalama/ramalama"
        config.runtime = "llama.cpp"

        mock_profile.return_value = HardwareProfile(
            architecture="x86_64",
            gpu=GpuInfo(gpu_type="cuda", driver_version=Version(12, 8, 0)),
            os_type="linux",
        )

        matrix = ImageCompatibilityMatrix(
            schema_version="1.0.0",
            default_image="quay.io/ramalama/ramalama",
            entries=[
                ImageEntry(
                    image="quay.io/ramalama/cuda",
                    constraints=ImageConstraints(
                        architectures=["x86_64"],
                        gpu_types=["cuda"],
                        runtimes=["llama.cpp"],
                        os_types=["linux"],
                    ),
                    priority=100,
                ),
            ],
        )
        mock_matrix.return_value = matrix

        result = select_image(config, runtime="llama.cpp")
        assert "cuda" in result

    @patch("ramalama.image_selector.detect_hardware_profile")
    @patch("ramalama.image_selector.load_image_matrix")
    @patch("ramalama.common.minor_release")
    def test_rocm_selection(self, mock_release, mock_matrix, mock_profile):
        """AMD GPU should select ROCm image."""
        mock_release.return_value = "0.17"
        config = MagicMock()
        config.is_set.return_value = False
        config.default_image = "quay.io/ramalama/ramalama"
        config.runtime = "llama.cpp"

        mock_profile.return_value = HardwareProfile(
            architecture="x86_64",
            gpu=GpuInfo(gpu_type="hip", driver_version=Version(6, 3, 0)),
            os_type="linux",
        )

        matrix = ImageCompatibilityMatrix(
            schema_version="1.0.0",
            default_image="quay.io/ramalama/ramalama",
            entries=[
                ImageEntry(
                    image="quay.io/ramalama/rocm",
                    constraints=ImageConstraints(
                        architectures=["x86_64"],
                        gpu_types=["hip"],
                        runtimes=["llama.cpp"],
                        os_types=["linux"],
                    ),
                    priority=100,
                ),
            ],
        )
        mock_matrix.return_value = matrix

        result = select_image(config, runtime="llama.cpp")
        assert "rocm" in result

    @patch("ramalama.image_selector.detect_hardware_profile")
    @patch("ramalama.image_selector.load_image_matrix")
    @patch("ramalama.common.minor_release")
    def test_vllm_runtime(self, mock_release, mock_matrix, mock_profile):
        """vLLM runtime should select vLLM image."""
        mock_release.return_value = "latest"
        config = MagicMock()
        config.is_set.return_value = False
        config.default_image = "quay.io/ramalama/ramalama"
        config.runtime = "vllm"

        mock_profile.return_value = HardwareProfile(
            architecture="x86_64",
            gpu=GpuInfo(gpu_type="cuda", driver_version=Version(12, 8, 0)),
            os_type="linux",
        )

        matrix = ImageCompatibilityMatrix(
            schema_version="1.0.0",
            default_image="quay.io/ramalama/ramalama",
            entries=[
                ImageEntry(
                    image="docker.io/vllm/vllm-openai",
                    constraints=ImageConstraints(
                        architectures=["x86_64"],
                        gpu_types=["cuda"],
                        runtimes=["vllm"],
                        os_types=["linux"],
                    ),
                    priority=50,
                ),
            ],
        )
        mock_matrix.return_value = matrix

        result = select_image(config, runtime="vllm")
        assert "vllm" in result

    @patch("ramalama.image_selector.detect_hardware_profile")
    @patch("ramalama.image_selector.load_image_matrix")
    @patch("ramalama.common.minor_release")
    def test_no_gpu_fallback(self, mock_release, mock_matrix, mock_profile):
        """No GPU should fallback to default image."""
        mock_release.return_value = "0.17"
        config = MagicMock()
        config.is_set.return_value = False
        config.default_image = "quay.io/ramalama/ramalama"
        config.runtime = "llama.cpp"

        mock_profile.return_value = HardwareProfile(
            architecture="x86_64",
            gpu=GpuInfo(gpu_type="none"),
            os_type="linux",
        )

        matrix = ImageCompatibilityMatrix(
            schema_version="1.0.0",
            default_image="quay.io/ramalama/ramalama",
            entries=[
                ImageEntry(
                    image="quay.io/ramalama/ramalama",
                    constraints=ImageConstraints(
                        architectures=["x86_64"],
                        gpu_types=["none"],
                        runtimes=["llama.cpp"],
                        os_types=["linux"],
                    ),
                    priority=1,
                ),
            ],
        )
        mock_matrix.return_value = matrix

        result = select_image(config, runtime="llama.cpp")
        assert result == "quay.io/ramalama/ramalama:0.17"

    @patch("ramalama.image_selector.detect_hardware_profile")
    @patch("ramalama.image_selector.load_image_matrix")
    @patch("ramalama.common.minor_release")
    def test_rag_image_selection(self, mock_release, mock_matrix, mock_profile):
        """RAG mode should select RAG-specific image."""
        mock_release.return_value = "0.17"
        config = MagicMock()
        config.is_set.return_value = False
        config.default_rag_image = "quay.io/ramalama/ramalama-rag"
        config.runtime = "llama.cpp"

        mock_profile.return_value = HardwareProfile(
            architecture="x86_64",
            gpu=GpuInfo(gpu_type="cuda", driver_version=Version(12, 8, 0)),
            os_type="linux",
        )

        matrix = ImageCompatibilityMatrix(
            schema_version="1.0.0",
            default_image="quay.io/ramalama/ramalama",
            entries=[
                ImageEntry(
                    image="quay.io/ramalama/cuda-rag",
                    constraints=ImageConstraints(
                        architectures=["x86_64"],
                        gpu_types=["cuda"],
                        runtimes=["llama.cpp-rag"],
                        os_types=["linux"],
                    ),
                    priority=100,
                ),
            ],
        )
        mock_matrix.return_value = matrix

        result = select_image(config, runtime="llama.cpp", is_rag=True)
        assert "rag" in result.lower()

    @patch("ramalama.image_selector.detect_hardware_profile")
    @patch("ramalama.image_selector.load_image_matrix")
    @patch("ramalama.common.minor_release")
    def test_fallback_tagging_no_matching_entries(self, mock_release, mock_matrix, mock_profile):
        """Fallback image should be tagged when no matrix entries match."""
        mock_release.return_value = "0.17"
        config = MagicMock()
        config.is_set.return_value = False
        config.default_image = "quay.io/ramalama/fallback"
        config.runtime = "llama.cpp"

        mock_profile.return_value = HardwareProfile(
            architecture="x86_64",
            gpu=GpuInfo(gpu_type="some_unknown_gpu"),
            os_type="linux",
        )

        matrix = ImageCompatibilityMatrix(
            schema_version="1.0.0",
            default_image="quay.io/ramalama/ramalama",
            entries=[],
        )
        mock_matrix.return_value = matrix

        result = select_image(config, runtime="llama.cpp")
        assert result == "quay.io/ramalama/fallback:0.17"


class TestGetHardwareSummary:
    """Tests for get_hardware_summary function."""

    @patch("ramalama.image_selector.detect_hardware_profile")
    def test_basic_summary(self, mock_profile):
        mock_profile.return_value = HardwareProfile(
            architecture="x86_64",
            gpu=GpuInfo(
                gpu_type="cuda",
                driver_version=Version(12, 8, 0),
                device_count=2,
            ),
            os_type="linux",
        )

        summary = get_hardware_summary()
        assert summary["architecture"] == "x86_64"
        assert summary["os_type"] == "linux"
        assert summary["gpu_type"] == "cuda"
        assert summary["gpu_device_count"] == "2"
        assert summary["gpu_driver_version"] == "12.8.0"

    @patch("ramalama.image_selector.detect_hardware_profile")
    def test_summary_with_memory(self, mock_profile):
        mock_profile.return_value = HardwareProfile(
            architecture="x86_64",
            gpu=GpuInfo(
                gpu_type="hip",
                memory_bytes=8_000_000_000,
            ),
            os_type="linux",
        )

        summary = get_hardware_summary()
        assert "gpu_memory_gb" in summary
        assert float(summary["gpu_memory_gb"]) == pytest.approx(7.5, rel=0.1)

    @patch("ramalama.image_selector.detect_hardware_profile")
    def test_summary_no_gpu(self, mock_profile):
        mock_profile.return_value = HardwareProfile(
            architecture="x86_64",
            gpu=GpuInfo(gpu_type="none"),
            os_type="linux",
        )

        summary = get_hardware_summary()
        assert summary["gpu_type"] == "none"
        assert "gpu_driver_version" not in summary
