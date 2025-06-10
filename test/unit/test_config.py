import os
from unittest.mock import patch

import pytest

from ramalama.config import DEFAULT_PORT, Config, ConfigLoader, get_engine, get_store, use_container


def test_defaults_are_set():
    cfg = Config()

    assert cfg.carimage == "registry.access.redhat.com/ubi9-micro:latest"
    assert cfg.container in [True, False]  # depends on env/system
    assert cfg.ctx_size == 2048
    assert cfg.engine in ["podman", "docker", None]
    assert cfg.env == []
    assert cfg.host == "0.0.0.0"
    assert cfg.image is None
    assert isinstance(cfg.images, dict)
    assert cfg.api == "none"
    assert cfg.keep_groups is False
    assert cfg.ngl == -1
    assert cfg.threads == -1
    assert cfg.nocontainer is False
    assert cfg.port == str(DEFAULT_PORT)
    assert cfg.pull == "newer"
    assert cfg.runtime == "llama.cpp"
    assert cfg.store == get_store()
    assert cfg.temp == "0.8"
    assert cfg.transport == "ollama"
    assert cfg.use_model_store is True
    assert cfg.ocr is False


def test_file_config_overrides_defaults():
    mock_file_config = {
        "image": "custom/image:latest",
        "threads": 8,
        "container": False,
    }

    with patch("ramalama.config.ConfigLoader.load_file_config", return_value=mock_file_config):
        with patch("ramalama.config.ConfigLoader.load_env_config", return_value={}):
            cfg = ConfigLoader.load()
            assert cfg.image == "custom/image:latest"
            assert cfg.threads == 8
            assert cfg.container is False


def test_env_overrides_file_and_default():
    mock_file_config = {
        "image": "custom/image:latest",
        "threads": 8,
    }
    mock_env_config = {
        "image": "env/image:override",
        "threads": 16,
    }

    with patch("ramalama.config.ConfigLoader.load_file_config", return_value=mock_file_config):
        with patch("ramalama.config.ConfigLoader.load_env_config", return_value=mock_env_config):
            cfg = ConfigLoader.load()
            assert cfg.image == "env/image:override"
            assert cfg.threads == 16


@pytest.mark.parametrize(
    "uid,is_root,expected",
    [
        (0, True, "/var/lib/ramalama"),
        (1000, False, os.path.expanduser("~/.local/share/ramalama")),
    ],
)
def test_get_store(uid, is_root, expected):
    with patch("os.geteuid", return_value=uid):
        assert get_store() == expected


@pytest.mark.parametrize(
    "env_value,expected",
    [
        ("true", True),
        ("false", False),
        (None, None),  # fallback to get_engine()
    ],
)
def test_use_container_env_override(env_value, expected):
    with patch.dict(os.environ, {"RAMALAMA_IN_CONTAINER": env_value} if env_value is not None else {}, clear=True):
        if expected is not None:
            assert use_container() is expected


@pytest.fixture(autouse=True)
def clear_get_engine_cache():
    get_engine.cache_clear()


class TestGetEngine:
    @pytest.mark.parametrize(
        "env_value,platform,expected",
        [
            ("podman", "linux", "podman"),
            ("docker", "linux", "docker"),
            ("docker", "darwin", "docker"),
            ("podman", "darwin", "podman"),
        ],
    )
    def test_get_engine_from_env(self, env_value, platform, expected):
        env = {"RAMALAMA_CONTAINER_ENGINE": env_value} if env_value is not None else {}
        with patch.dict(os.environ, env):
            with patch("sys.platform", platform):
                assert get_engine() == expected

    def test_get_engine_from_env_podman_on_osx(self):
        with patch.dict(os.environ, {"RAMALAMA_CONTAINER_ENGINE": "podman"}):
            with patch("sys.platform", "darwin"):
                with patch("ramalama.config.apple_vm") as mock_apple_vm:
                    get_engine()
                    mock_apple_vm.assert_called_once_with("podman")

    def test_get_engine_from_env_docker_on_osx(self):
        with patch.dict(os.environ, {"RAMALAMA_CONTAINER_ENGINE": "docker"}):
            with patch("sys.platform", "darwin"):
                with patch("ramalama.config.apple_vm") as mock_apple_vm:
                    get_engine()
                    mock_apple_vm.assert_not_called()

    def test_get_engine_with_toolboxenv(self):
        with patch("os.getenv", return_value=None):
            with patch("os.path.exists", side_effect=lambda x: x == "/run/.toolboxenv"):
                assert get_engine() is None

    @pytest.mark.parametrize(
        "platform,expected",
        [
            ("darwin", None),
            ("linux", "podman"),
        ],
    )
    def test_get_engine_with_podman_available(self, platform, expected):
        with patch("ramalama.config.available", side_effect=lambda x: x == "podman"):
            with patch("sys.platform", platform):
                assert get_engine() == expected

    def test_get_engine_with_podman_available_osx_apple_vm_has_podman(self):
        with patch("ramalama.config.available", side_effect=lambda x: x == "podman"):
            with patch("sys.platform", "darwin"):
                with patch("ramalama.config.apple_vm", side_effect=lambda x: x == "podman"):
                    assert get_engine() == "podman"

    def test_get_engine_with_podman_available_on_osx(self):
        with patch("ramalama.config.available", side_effect=lambda x: x == "podman"):
            with patch("sys.platform", "darwin"):
                with patch("ramalama.config.apple_vm") as mock_apple_vm:
                    assert get_engine() == "podman"
                    mock_apple_vm.assert_called_once_with("podman")

    def test_get_engine_with_docker_available_osx(self):
        with patch("ramalama.config.available", side_effect=lambda x: x == "docker"):
            with patch("sys.platform", "darwin"):
                assert get_engine() is None

    def test_get_engine_with_docker_available_linux(self):
        with patch("ramalama.config.available", side_effect=lambda x: x == "docker"):
            with patch("sys.platform", "linux"):
                assert get_engine() == "docker"
