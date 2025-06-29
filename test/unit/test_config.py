import os
from unittest.mock import patch

import pytest

from ramalama.config import DEFAULT_PORT, default_config, get_default_engine, get_default_store


def test_correct_config_defaults():
    cfg = default_config()

    assert cfg.carimage == "registry.access.redhat.com/ubi9-micro:latest"
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
    assert cfg.nocontainer is False
    assert cfg.port == str(DEFAULT_PORT)
    assert cfg.pull == "newer"
    assert cfg.runtime == "llama.cpp"
    assert cfg.store == get_default_store()
    assert cfg.temp == "0.8"
    assert cfg.transport == "ollama"
    assert cfg.ocr is False


def test_config_defaults_not_set():
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
    assert cfg.is_set("nocontainer") is False
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
        assert cfg.container == expected


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
            ("darwin", None),
            ("linux", "podman"),
        ],
    )
    def test_get_default_engine_with_podman_available(self, platform, expected):
        with patch("ramalama.config.available", side_effect=lambda x: x == "podman"):
            with patch("sys.platform", platform):
                with patch("ramalama.config.apple_vm", return_value=False):
                    assert get_default_engine() == expected

    def test_get_default_engine_with_podman_available_osx_apple_vm_has_podman(self):
        with patch("ramalama.config.available", side_effect=lambda x: x == "podman"):
            with patch("sys.platform", "darwin"):
                with patch("ramalama.config.apple_vm", side_effect=lambda x: x == "podman"):
                    assert get_default_engine() == "podman"

    def test_get_default_engine_triggers_apple_vm_check_on_osx(self):
        with patch("ramalama.config.available", side_effect=lambda x: x == "podman"):
            with patch("sys.platform", "darwin"):
                with patch("ramalama.config.apple_vm") as mock_apple_vm:
                    assert get_default_engine() == "podman"
                    mock_apple_vm.assert_called_once_with("podman")

    def test_get_default_engine_with_docker_available_osx(self):
        with patch("ramalama.config.available", side_effect=lambda x: x == "docker"):
            with patch("sys.platform", "darwin"):
                assert get_default_engine() is None

    def test_get_default_engine_with_docker_available_linux(self):
        with patch("ramalama.config.available", side_effect=lambda x: x == "docker"):
            with patch("sys.platform", "linux"):
                assert get_default_engine() == "docker"
