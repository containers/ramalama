import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping

from ramalama.common import available
from ramalama.layered_config import LayeredMixin, deep_merge
from ramalama.toml_parser import TOMLParser

PathStr = str
DEFAULT_PORT_RANGE: tuple[int, int] = (8080, 8090)
DEFAULT_PORT: int = DEFAULT_PORT_RANGE[0]
DEFAULT_IMAGE = "quay.io/ramalama/ramalama"
SUPPORTED_ENGINES = Literal["podman", "docker"] | PathStr
SUPPORTED_RUNTIMES = Literal["llama.cpp", "vllm", "mlx"]
COLOR_OPTIONS = Literal["auto", "always", "never"]


def get_default_engine() -> SUPPORTED_ENGINES | None:
    """Determine the container manager to use based on environment and platform."""
    if os.path.exists("/run/.toolboxenv"):
        return None

    if available("podman"):
        return "podman"

    return "docker" if available("docker") and sys.platform != "darwin" else None


def get_default_store() -> str:
    if os.geteuid() == 0:
        return "/var/lib/ramalama"

    return os.path.expanduser("~/.local/share/ramalama")


def coerce_to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    elif isinstance(value, str):
        val = value.strip().lower()
        if val in {"on", "true", "1", "yes", "y"}:
            return True
        elif val in {"off", "false", "0", "no", "n"}:
            return False
    raise ValueError(f"Cannot coerce {value!r} to bool")


@dataclass
class UserConfig:
    no_missing_gpu_prompt: bool = False

    def __post_init__(self):
        self.no_missing_gpu_prompt = coerce_to_bool(self.no_missing_gpu_prompt)


@dataclass
class RamalamaSettings:
    """These settings are not managed directly by the user"""

    config_file: str | None = None


@dataclass
class BaseConfig:
    container: bool = None  # type: ignore
    image: str = None  # type: ignore
    carimage: str = "registry.access.redhat.com/ubi10-micro:latest"
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
    port: str = str(DEFAULT_PORT)
    pull: str = "newer"
    rag_format: Literal["qdrant", "json", "markdown"] = "qdrant"
    runtime: SUPPORTED_RUNTIMES = "llama.cpp"
    store: str = field(default_factory=get_default_store)
    temp: str = "0.8"
    transport: str = "ollama"
    ocr: bool = False
    default_image: str = DEFAULT_IMAGE
    user: UserConfig = field(default_factory=UserConfig)
    selinux: bool = False
    settings: RamalamaSettings = field(default_factory=RamalamaSettings)

    def __post_init__(self):
        self.container = coerce_to_bool(self.container) if self.container is not None else self.engine is not None
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
        config = config.get("ramalama", {})
        config['settings'] = {'config_file': config_path}
        return config

    config = {}
    config_paths = [
        "/usr/share/ramalama/ramalama.conf",
        "/usr/local/share/ramalama/ramalama.conf",
        "/etc/ramalama/ramalama.conf",
        os.path.expanduser(os.path.join(os.getenv("XDG_CONFIG_HOME", "~/.config"), "ramalama", "ramalama.conf")),
    ]

    config_path = None
    for path in config_paths:
        if os.path.exists(path):
            config = parser.parse_file(path)

        path_str = f"{path}.d"
        if os.path.isdir(path_str):
            for conf_file in sorted(Path(path_str).glob("*.conf")):
                deep_merge(config, parser.parse_file(conf_file))

        if config:
            config = config.get('ramalama', {})
            config['settings'] = {'config_file': config_path}
            return config

    return {}


def load_env_config(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    if env is None:
        env = os.environ

    config = {}
    for k, v in env.items():
        if not k.startswith("RAMALAMA"):
            continue

        k = k[8:].lstrip('_')
        subkeys = k.split("__")

        subconf = config
        for key in subkeys[:-1]:
            conf_key = key.lower()
            subconf.setdefault(conf_key, {})
            subconf = subconf[conf_key]

        subconf[subkeys[-1].lower()] = v

    if container := config.pop('in_container', None):
        config['container'] = coerce_to_bool(container)

    if container_engine := config.pop('container_engine', None):
        config['engine'] = container_engine

    if 'env' in config:
        config['env'] = config['env'].split(',')

    if 'images' in config:
        config['images'] = json.loads(config['images'])

    for key in ['ocr', 'keep_groups', 'container']:
        if key in config:
            config[key] = coerce_to_bool(config[key])

    for key in ['threads', 'ctx_size', 'ngl']:
        if key in config:
            config[key] = int(config[key])
    return config


def default_config(env: Mapping[str, str] | None = None) -> Config:
    """Returns a default Config object with all layers initialized."""
    return Config(load_env_config(env), load_file_config())


CONFIG = default_config()
