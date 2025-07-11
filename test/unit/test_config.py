import os
from unittest.mock import patch

import pytest

from ramalama.config import DEFAULT_PORT, default_config, get_default_engine, get_default_store, load_env_config


def test_correct_config_defaults(monkeypatch):
    monkeypatch.delenv("RAMALAMA_IMAGE", raising=False)
    cfg = default_config()

    assert cfg.carimage == "registry.access.redhat.com/ubi10-micro:latest"
    assert cfg.container in [True, False]  # depends on env/system
    assert cfg.ctx_size == 2048
    assert cfg.engine in ["podman", "docker", None]
    assert cfg.env == []
    assert cfg.host == "0.0.0.0"
    assert cfg.image == cfg.default_image
    assert isinstance(cfg.images, dict)
    assert cfg.api == "none"
    assert cfg.keep_groups is False
    assert cfg.ngl == -1
    assert cfg.threads == -1
    assert cfg.port == str(DEFAULT_PORT)
    assert cfg.pull == "newer"
    assert cfg.runtime == "llama.cpp"
    assert cfg.store == get_default_store()
    assert cfg.temp == "0.8"
    assert cfg.transport == "ollama"
    assert cfg.ocr is False


def test_config_defaults_not_set(monkeypatch):
    monkeypatch.delenv("RAMALAMA_IMAGE", raising=False)
    cfg = default_config()

    assert cfg.is_set("carimage") is False
    assert cfg.is_set("container") is False  # depends on env/system
    assert cfg.is_set("ctx_size") is False
    assert cfg.is_set("engine") is False
    assert cfg.is_set("env") is False
    assert cfg.is_set("host") is False
    assert cfg.is_set("image") is False
    assert cfg.is_set("images") is False
    assert cfg.is_set("api") is False
    assert cfg.is_set("keep_groups") is False
    assert cfg.is_set("ngl") is False
    assert cfg.is_set("threads") is False
    assert cfg.is_set("port") is False
    assert cfg.is_set("pull") is False
    assert cfg.is_set("runtime") is False
    assert cfg.is_set("store") is False
    assert cfg.is_set("temp") is False
    assert cfg.is_set("transport") is False
    assert cfg.is_set("ocr") is False


def test_file_config_overrides_defaults():
    mock_file_config = {
        "image": "custom/image:latest",
        "threads": 8,
        "container": False,
    }

    with patch("ramalama.config.load_file_config", return_value=mock_file_config):
        with patch("ramalama.config.load_env_config", return_value={}):
            cfg = default_config()
            assert cfg.image == "custom/image:latest"
            assert cfg.threads == 8
            assert cfg.container is False

            assert cfg.is_set("image") is True
            assert cfg.is_set("threads") is True
            assert cfg.is_set("container") is True


def test_env_overrides_file_and_default():
    mock_file_config = {
        "image": "custom/image:latest",
        "threads": 8,
    }
    mock_env_config = {
        "image": "env/image:override",
        "threads": 16,
    }

    with patch("ramalama.config.load_file_config", return_value=mock_file_config):
        with patch("ramalama.config.load_env_config", return_value=mock_env_config):
            cfg = default_config()
            assert cfg.image == "env/image:override"
            assert cfg.threads == 16

            assert cfg.is_set("image") is True
            assert cfg.is_set("threads") is True


@pytest.mark.parametrize(
    "uid,is_root,expected",
    [
        (0, True, "/var/lib/ramalama"),
        (1000, False, os.path.expanduser("~/.local/share/ramalama")),
    ],
)
def test_get_default_store(uid, is_root, expected):
    with patch("os.geteuid", return_value=uid):
        assert get_default_store() == expected


@pytest.mark.parametrize(
    "env_value,expected",
    [
        ("true", True),
        ("false", False),
        ("True", True),
        ("False", False),
    ],
)
def test_cfg_container_env_override(env_value, expected):
    with patch.dict(os.environ, {"RAMALAMA_IN_CONTAINER": env_value} if env_value is not None else {}, clear=True):
        cfg = default_config()
        assert cfg.is_set("container") is True
        print(os.environ)
        assert cfg.container == expected, cfg.container


def test_cfg_container_not_set():
    with patch.dict(os.environ, {"RAMALAMA_CONTAINER_ENGINE": "podman"}):
        cfg = default_config()
        assert cfg.is_set("container") is False
        assert cfg.container is True

    with patch.dict(os.environ, {}):
        cfg = default_config()
        with patch("ramalama.config.load_env_config", return_value={}):
            assert cfg.is_set("container") is False
            assert cfg.container is (cfg.engine is not None)


class TestGetDefaultEngine:

    def test_get_default_engine_with_toolboxenv(self):
        with patch("os.getenv", return_value=None):
            with patch("os.path.exists", side_effect=lambda x: x == "/run/.toolboxenv"):
                assert get_default_engine() is None

    @pytest.mark.parametrize(
        "platform,expected",
        [
            ("darwin", "podman"),
            ("linux", "podman"),
        ],
    )
    def test_get_default_engine_with_podman_available(self, platform, expected):
        with patch("ramalama.config.available", side_effect=lambda x: x == "podman"):
            with patch("sys.platform", platform):
                assert get_default_engine() == expected

    def test_get_default_engine_with_podman_available_osx_apple_vm_has_podman(self):
        with patch("ramalama.config.available", side_effect=lambda x: x == "podman"):
            with patch("sys.platform", "darwin"):
                assert get_default_engine() == "podman"

    def test_get_default_engine_with_docker_available_osx(self):
        with patch("ramalama.config.available", side_effect=lambda x: x == "docker"):
            with patch("sys.platform", "darwin"):
                assert get_default_engine() is None

    def test_get_default_engine_with_docker_available_linux(self):
        with patch("ramalama.config.available", side_effect=lambda x: x == "docker"):
            with patch("sys.platform", "linux"):
                assert get_default_engine() == "docker"


class TestLoadEnvConfig:
    """Test the load_env_config function for arbitrary environment variable loading."""

    def test_load_env_config_basic_variables(self):
        """Test loading basic RAMALAMA environment variables."""
        env = {
            "RAMALAMA_IMAGE": "test/image:latest",
            "RAMALAMA_THREADS": "8",
            "RAMALAMA_CONTAINER": "true",
            "RAMALAMA_HOST": "127.0.0.1",
        }

        result = load_env_config(env)

        expected = {
            "image": "test/image:latest",
            "threads": 8,
            "container": True,
            "host": "127.0.0.1",
        }
        assert result == expected

    def test_load_env_config_nested_variables(self):
        """Test loading nested configuration via double underscores."""
        env = {
            "RAMALAMA_USER__NO_MISSING_GPU_PROMPT": "true",
            "RAMALAMA_SETTINGS__CONFIG_FILE": "/path/to/config",
            "RAMALAMA_IMAGES": '{"CUDA_VISIBLE_DEVICES": "custom/cuda:latest"}',
        }

        result = load_env_config(env)

        expected = {
            "user": {"no_missing_gpu_prompt": "true"},
            "settings": {"config_file": "/path/to/config"},
            "images": {"CUDA_VISIBLE_DEVICES": "custom/cuda:latest"},
        }

        assert result == expected

    def test_load_env_config_deeply_nested_variables(self):
        """Test loading deeply nested configuration."""
        env = {
            "RAMALAMA_DATABASE__CONNECTION__HOST": "localhost",
            "RAMALAMA_DATABASE__CONNECTION__PORT": "5432",
            "RAMALAMA_DATABASE__CREDENTIALS__USERNAME": "user",
            "RAMALAMA_DATABASE__CREDENTIALS__PASSWORD": "pass",
        }

        result = load_env_config(env)

        expected = {
            "database": {
                "connection": {"host": "localhost", "port": "5432"},
                "credentials": {"username": "user", "password": "pass"},
            }
        }
        assert result == expected

    def test_load_env_config_legacy_variables(self):
        """Test loading legacy environment variables."""
        env = {
            "RAMALAMA_IN_CONTAINER": "true",
            "RAMALAMA_CONTAINER_ENGINE": "docker",
        }

        result = load_env_config(env)

        expected = {
            "container": True,
            "engine": "docker",
        }
        assert result == expected

    def test_load_env_config_mixed_legacy_and_new(self):
        """Test loading both legacy and new environment variables."""
        env = {
            "RAMALAMA_IN_CONTAINER": "true",
            "RAMALAMA_CONTAINER_ENGINE": "docker",
            "RAMALAMA_IMAGE": "test/image:latest",
            "RAMALAMA_USER__NO_MISSING_GPU_PROMPT": "true",
        }

        result = load_env_config(env)

        expected = {
            "container": True,
            "engine": "docker",
            "image": "test/image:latest",
            "user": {"no_missing_gpu_prompt": "true"},
        }
        assert result == expected

    def test_load_env_config_ignores_non_ramalama_vars(self):
        """Test that non-RAMALAMA environment variables are ignored."""
        env = {
            "RAMALAMA_IMAGE": "test/image:latest",
            "PATH": "/usr/bin:/bin",
            "HOME": "/home/user",
            "RAMALAMA_THREADS": "8",
            "SHELL": "/bin/bash",
        }

        result = load_env_config(env)

        expected = {
            "image": "test/image:latest",
            "threads": 8,
        }
        assert result == expected

    def test_load_env_config_empty_environment(self):
        """Test loading from empty environment."""
        result = load_env_config({})
        assert result == {}

    def test_load_env_config_none_environment(self):
        """Test loading with None environment (should use os.environ)."""
        with patch("os.environ", {"RAMALAMA_IMAGE": "test/image:latest"}):
            result = load_env_config()
            assert result == {"image": "test/image:latest"}

    def test_load_env_config_case_insensitive_keys(self):
        """Test that keys are converted to lowercase."""
        env = {
            "RAMALAMA_IMAGE": "test/image:latest",
            "RAMALAMA_THREADS": "8",
            "RAMALAMA_USER__NO_MISSING_GPU_PROMPT": "true",
        }

        result = load_env_config(env)

        # All keys should be lowercase
        assert "image" in result
        assert "threads" in result
        assert "user" in result
        assert "no_missing_gpu_prompt" in result["user"]

    def test_load_env_config_single_underscore_prefix(self):
        """Test handling of single underscore prefix."""
        env = {
            "RAMALAMA_IMAGE": "test/image:latest",
            "RAMALAMA__NESTED__VALUE": "nested_value",
        }

        result = load_env_config(env)

        expected = {"image": "test/image:latest", "nested": {"value": "nested_value"}}
        assert result == expected

    def test_load_env_config_double_underscore_prefix(self):
        """Test handling of double underscore prefix."""
        env = {
            "RAMALAMA__DEEP__NESTED__VALUE": "deep_value",
        }

        result = load_env_config(env)

        expected = {"deep": {"nested": {"value": "deep_value"}}}
        assert result == expected

    def test_load_env_config_mixed_underscore_prefixes(self):
        """Test handling of mixed underscore prefixes."""
        env = {
            "RAMALAMA_IMAGE": "test/image:latest",
            "RAMALAMA__NESTED__VALUE": "nested_value",
            "RAMALAMA___TRIPLE___VALUE": "triple_value",
        }

        result = load_env_config(env)

        expected = {
            "image": "test/image:latest",
            "nested": {"value": "nested_value"},
            "triple": {"_value": "triple_value"},
        }
        assert result == expected

    def test_load_env_config_empty_subkeys(self):
        """Test handling of empty subkeys."""
        env = {
            "RAMALAMA__": "empty_prefix",
            "RAMALAMA___": "triple_underscore",
        }

        result = load_env_config(env)

        expected = {
            "": "triple_underscore",  # This will overwrite the previous one
        }
        assert result == expected

    def test_load_env_config_special_characters(self):
        """Test handling of special characters in values."""
        env = {
            "RAMALAMA_STRING_VALUE": "test with spaces",
            "RAMALAMA_NUMBER_VALUE": "123",
            "RAMALAMA_BOOL_VALUE": "true",
            "RAMALAMA_SPECIAL_VALUE": "test@example.com",
        }

        result = load_env_config(env)

        expected = {
            "string_value": "test with spaces",
            "number_value": "123",
            "bool_value": "true",
            "special_value": "test@example.com",
        }
        assert result == expected

    def test_load_env_config_complex_nesting(self):
        """Test complex nesting scenarios."""
        env = {
            "RAMALAMA_APP__DATABASE__HOST": "localhost",
            "RAMALAMA_APP__DATABASE__PORT": "5432",
            "RAMALAMA_APP__LOGGING__LEVEL": "debug",
            "RAMALAMA_APP__LOGGING__FILE": "/var/log/app.log",
            "RAMALAMA_APP__FEATURES__ENABLED": "true",
            "RAMALAMA_APP__FEATURES__MAX_CONNECTIONS": "100",
        }

        result = load_env_config(env)

        expected = {
            "app": {
                "database": {"host": "localhost", "port": "5432"},
                "logging": {"level": "debug", "file": "/var/log/app.log"},
                "features": {"enabled": "true", "max_connections": "100"},
            }
        }
        assert result == expected

    def test_debug_images_loading(self):
        """Debug test to see what load_env_config returns for images."""
        env = {
            "RAMALAMA_IMAGES": (
                '{"CUDA_VISIBLE_DEVICES": "custom/cuda:latest", "INTEL_VISIBLE_DEVICES": "custom/intel:latest"}'
            ),
        }

        result = load_env_config(env)
        print(f"load_env_config result: {result}")

        # Should contain the parsed images dict
        assert "images" in result
        assert result["images"] == {
            "CUDA_VISIBLE_DEVICES": "custom/cuda:latest",
            "INTEL_VISIBLE_DEVICES": "custom/intel:latest",
        }


class TestConfigIntegration:
    """Integration tests for the complete config system with deep merge and env loading."""

    def test_config_with_nested_env_variables(self):
        """Test that nested environment variables are properly loaded and merged."""
        env = {
            "RAMALAMA_USER__NO_MISSING_GPU_PROMPT": "true",
            "RAMALAMA_SETTINGS__CONFIG_FILE": "/custom/config.toml",
            "RAMALAMA_IMAGES": (
                '{"CUDA_VISIBLE_DEVICES": "custom/cuda:latest", "HIP_VISIBLE_DEVICES": "custom/rocm:latest"}'
            ),
        }

        with patch("ramalama.config.load_file_config", return_value={}):
            cfg = default_config(env)

            assert cfg.user.no_missing_gpu_prompt is True
            assert cfg.settings.config_file == "/custom/config.toml"
            assert cfg.images["CUDA_VISIBLE_DEVICES"] == "custom/cuda:latest"
            assert cfg.images["HIP_VISIBLE_DEVICES"] == "custom/rocm:latest"

            assert cfg.is_set("user") is True
            assert cfg.is_set("settings") is True
            assert cfg.is_set("images") is True

    def test_config_env_overrides_file_config(self):
        """Test that environment variables override file config."""
        file_config = {
            "image": "file/image:latest",
            "threads": 4,
            "user": {"no_missing_gpu_prompt": False},
            "images": {"CUDA_VISIBLE_DEVICES": "file/cuda:latest"},
        }

        env = {
            "RAMALAMA_IMAGE": "env/image:latest",
            "RAMALAMA_THREADS": "8",
            "RAMALAMA_USER__NO_MISSING_GPU_PROMPT": "true",
            "RAMALAMA_IMAGES": '{"CUDA_VISIBLE_DEVICES": "env/cuda:latest"}',
        }

        with patch("ramalama.config.load_file_config", return_value=file_config):
            cfg = default_config(env)

            # Environment should override file config
            assert cfg.image == "env/image:latest"
            assert cfg.threads == 8
            assert cfg.user.no_missing_gpu_prompt is True
            assert cfg.images["CUDA_VISIBLE_DEVICES"] == "env/cuda:latest"

    def test_config_multiple_env_layers(self):
        """Test that multiple environment variable layers work correctly."""
        env = {
            "RAMALAMA_IMAGE": "base/image:latest",
            "RAMALAMA_THREADS": "4",
            "RAMALAMA_USER__NO_MISSING_GPU_PROMPT": "false",
            "RAMALAMA_IMAGES": '{"CUDA_VISIBLE_DEVICES": "base/cuda:latest"}',
            "RAMALAMA_APP__DATABASE__HOST": "localhost",
            "RAMALAMA_APP__DATABASE__PORT": "5432",
        }

        with patch("ramalama.config.load_file_config", return_value={}):
            cfg = default_config(env)

            # Basic config should work
            assert cfg.image == "base/image:latest"
            assert cfg.threads == 4
            assert cfg.user.no_missing_gpu_prompt is False
            assert cfg.images["CUDA_VISIBLE_DEVICES"] == "base/cuda:latest"

            # Arbitrary nested config should be available
            # Note: This would require the config to support arbitrary fields
            # For now, we just verify the basic functionality works

    def test_config_legacy_compatibility(self):
        """Test that legacy environment variables still work."""
        env = {
            "RAMALAMA_IN_CONTAINER": "true",
            "RAMALAMA_CONTAINER_ENGINE": "docker",
            "RAMALAMA_IMAGE": "test/image:latest",
        }

        with patch("ramalama.config.load_file_config", return_value={}):
            cfg = default_config(env)

            assert cfg.container is True
            assert cfg.engine == "docker"
            assert cfg.image == "test/image:latest"

    def test_config_empty_layers(self):
        """Test behaviour with empty configuration layers."""
        with patch("ramalama.config.load_file_config", return_value={}):
            cfg = default_config({})

            # Should use defaults
            assert cfg.image == cfg.default_image
            assert cfg.threads == -1
            assert cfg.user.no_missing_gpu_prompt is False

    def test_config_type_coercion(self):
        """Test that environment variables are properly type-coerced."""
        env = {
            "RAMALAMA_THREADS": "16",
            "RAMALAMA_CTX_SIZE": "4096",
            "RAMALAMA_NGL": "2",
            "RAMALAMA_CONTAINER": "true",
            "RAMALAMA_KEEP_GROUPS": "true",
            "RAMALAMA_OCR": "true",
            "RAMALAMA_USER__NO_MISSING_GPU_PROMPT": "true",
        }

        with patch("ramalama.config.load_file_config", return_value={}):
            cfg = default_config(env)

            assert cfg.threads == 16
            assert cfg.ctx_size == 4096
            assert cfg.ngl == 2
            assert cfg.container is True
            assert cfg.keep_groups is True
            assert cfg.ocr is True
            assert cfg.user.no_missing_gpu_prompt is True

    def test_config_complex_nesting_scenario(self):
        """Test a complex real-world nesting scenario."""
        file_config = {
            "images": {
                "CUDA_VISIBLE_DEVICES": "quay.io/ramalama/cuda:latest",
                "HIP_VISIBLE_DEVICES": "quay.io/ramalama/rocm:latest",
            },
            "user": {"no_missing_gpu_prompt": False},
        }

        env = {
            "RAMALAMA_IMAGE": "custom/ramalama:latest",
            "RAMALAMA_THREADS": "8",
            "RAMALAMA_IMAGES": (
                '{"CUDA_VISIBLE_DEVICES": "custom/cuda:latest", "INTEL_VISIBLE_DEVICES": "custom/intel:latest"}'
            ),
            "RAMALAMA_USER__NO_MISSING_GPU_PROMPT": "true",
            "RAMALAMA_APP__LOGGING__LEVEL": "debug",
            "RAMALAMA_APP__LOGGING__FILE": "/var/log/ramalama.log",
        }

        with patch("ramalama.config.load_file_config", return_value=file_config):
            cfg = default_config(env)

            # Verify the merged configuration
            assert cfg.image == "custom/ramalama:latest"
            assert cfg.threads == 8
            assert cfg.user.no_missing_gpu_prompt is True

            # Deep merged images
            expected_images = {
                "CUDA_VISIBLE_DEVICES": "custom/cuda:latest",  # from env
                "INTEL_VISIBLE_DEVICES": "custom/intel:latest",  # from env
                "HIP_VISIBLE_DEVICES": "quay.io/ramalama/rocm:latest",  # from file config
            }
            assert cfg.images == expected_images

    def test_config_is_set_behavior(self):
        """Test that is_set correctly tracks configuration sources."""
        file_config = {
            "image": "file/image:latest",
            "threads": 4,
        }

        env = {
            "RAMALAMA_IMAGE": "env/image:latest",
            "RAMALAMA_USER__NO_MISSING_GPU_PROMPT": "true",
        }

        with patch("ramalama.config.load_file_config", return_value=file_config):
            cfg = default_config(env)

            # Values set in either layer should return True
            assert cfg.is_set("image") is True
            assert cfg.is_set("threads") is True
            assert cfg.is_set("user") is True

            # Values not set in any layer should return False
            assert cfg.is_set("host") is False
            assert cfg.is_set("port") is False
