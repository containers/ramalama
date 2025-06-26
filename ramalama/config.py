import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping

from ramalama.common import apple_vm, available
from ramalama.layered_config import LayeredMixin
from ramalama.toml_parser import TOMLParser

DEFAULT_PORT_RANGE: tuple[int, int] = (8080, 8090)
DEFAULT_PORT: int = DEFAULT_PORT_RANGE[0]
DEFAULT_IMAGE = "quay.io/ramalama/ramalama"
SUPPORTED_ENGINES = Literal["podman", "docker"] | os.PathLike[str]


def get_default_engine() -> SUPPORTED_ENGINES | None:
    """Determine the container manager to use based on environment and platform."""
    if os.path.exists("/run/.toolboxenv"):
        return None

    if available("podman") and (sys.platform != "darwin" or apple_vm("podman")):
        return "podman"

    return "docker" if available("docker") and sys.platform != "darwin" else None


def get_default_store() -> str:
    if os.geteuid() == 0:
        return "/var/lib/ramalama"

    return os.path.expanduser("~/.local/share/ramalama")


@dataclass
class BaseConfig:
    container: bool = None  # type: ignore
    image: str = None  # type: ignore
    carimage: str = "registry.access.redhat.com/ubi9-micro:latest"
    ctx_size: int = 2048
    engine: SUPPORTED_ENGINES | None = field(default_factory=get_default_engine)
    env: list[str] = field(default_factory=list)
    host: str = "0.0.0.0"
    images: dict[str, str] = field(
        default_factory=lambda: {
            "ASAHI_VISIBLE_DEVICES": "quay.io/ramalama/asahi",
            "ASCEND_VISIBLE_DEVICES": "quay.io/ramalama/cann",
            "CUDA_VISIBLE_DEVICES": "quay.io/ramalama/cuda",
            "GGML_VK_VISIBLE_DEVICES": "quay.io/ramalama/ramalama",
            "HIP_VISIBLE_DEVICES": "quay.io/ramalama/rocm",
            "INTEL_VISIBLE_DEVICES": "quay.io/ramalama/intel-gpu",
            "MUSA_VISIBLE_DEVICES": "quay.io/ramalama/musa",
        }
    )
    api: str = "none"
    keep_groups: bool = False
    ngl: int = -1
    threads: int = -1
    nocontainer: bool = False
    port: str = str(DEFAULT_PORT)
    pull: str = "newer"
    runtime: str = "llama.cpp"
    store: str = field(default_factory=get_default_store)
    temp: str = "0.8"
    transport: str = "ollama"
    ocr: bool = False
    default_image: str = DEFAULT_IMAGE

    def __post_init__(self):
        self.container = self.container if self.container is not None else self.engine is not None
        self.image = self.image if self.image is not None else self.default_image


class Config(LayeredMixin, BaseConfig):
    """
    Config class that combines multiple configuration layers to create a complete BaseConfig.
    Exposes the same attributes as BaseConfig, but allows for dynamic loading of configuration layers.
    Mixins should be inherited first.
    """

    pass


def load_file_config() -> dict[str, Any]:
    parser = TOMLParser()
    config_path = os.getenv("RAMALAMA_CONFIG")

    if config_path and os.path.exists(config_path):
        config = parser.parse_file(config_path)
        return config.get("ramalama", {})

    config = {}
    config_paths = [
        "/usr/share/ramalama/ramalama.conf",
        "/usr/local/share/ramalama/ramalama.conf",
        "/etc/ramalama/ramalama.conf",
        os.path.expanduser(os.path.join(os.getenv("XDG_CONFIG_HOME", "~/.config"), "ramalama", "ramalama.conf")),
    ]

    for path in config_paths:
        if os.path.exists(path):
            config = parser.parse_file(path)

        path_str = f"{path}.d"
        if os.path.isdir(path_str):
            for conf_file in sorted(Path(path_str).glob("*.conf")):
                config = parser.parse_file(conf_file)

    return config.get("ramalama", {})


def load_env_config(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    if env is None:
        env = os.environ

    envvars = {
        'engine': 'RAMALAMA_CONTAINER_ENGINE',
        'image': 'RAMALAMA_IMAGE',
        'store': 'RAMALAMA_STORE',
        'transport': 'RAMALAMA_TRANSPORT',
        'api': 'RAMALAMA_API',
    }
    config: dict[str, Any] = {k: value for k, v in envvars.items() if (value := env.get(v)) is not None}

    if container := env.get('RAMALAMA_IN_CONTAINER'):
        config['container'] = container.lower() == 'true'
    return config


def default_config(env: Mapping[str, str] | None = None) -> Config:
    """Returns a default Config object with all layers initialized."""
    return Config(load_env_config(env), load_file_config())


CONFIG = default_config()
