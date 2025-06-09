import os
import sys
from collections import ChainMap
from pathlib import Path
from typing import Any, Dict
from dataclasses import dataclass, field
from functools import lru_cache
from ramalama.toml_parser import TOMLParser
from ramalama.arg_types import ENGINE_TYPES
from ramalama.common import available, apple_vm

DEFAULT_PORT_RANGE: tuple[int] = (8080, 8090)
DEFAULT_PORT: int = DEFAULT_PORT_RANGE[0]
DEFAULT_IMAGE = "quay.io/ramalama/ramalama"


@lru_cache(maxsize=1)
def get_engine() -> ENGINE_TYPES | None:
    engine = os.getenv("RAMALAMA_CONTAINER_ENGINE")
    if engine is not None:
        if os.path.basename(engine) == "podman" and sys.platform == "darwin":
            # apple_vm triggers setting global variable podman_machine_accel side effect
            apple_vm(engine)
        return engine

    if os.path.exists("/run/.toolboxenv"):
        return None

    if available("podman") and (sys.platform != "darwin" or apple_vm("podman")):
        return "podman"

    if available("docker") and sys.platform != "darwin":
        return "docker"
    
    return None


def get_store() -> str:
    if os.geteuid() == 0:
        return "/var/lib/ramalama"

    return os.path.expanduser("~/.local/share/ramalama")


def use_container() -> bool:
    use_container = os.getenv("RAMALAMA_IN_CONTAINER")
    if use_container:
        return use_container.lower() == "true"

    engine = get_engine()
    return engine is not None


@dataclass
class Config:
    carimage: str = "registry.access.redhat.com/ubi9-micro:latest"
    container: bool = field(default_factory=use_container)
    ctx_size: int = 2048
    engine: ENGINE_TYPES | None = field(default_factory=get_engine)
    env: list[str] = field(default_factory=list)
    host: str = "0.0.0.0"
    image: str | None = None
    images: dict[str, str] = field(default_factory=lambda: {
        "ASAHI_VISIBLE_DEVICES": "quay.io/ramalama/asahi",
        "ASCEND_VISIBLE_DEVICES": "quay.io/ramalama/cann",
        "CUDA_VISIBLE_DEVICES": "quay.io/ramalama/cuda",
        "HIP_VISIBLE_DEVICES": "quay.io/ramalama/rocm",
        "INTEL_VISIBLE_DEVICES": "quay.io/ramalama/intel-gpu",
        "MUSA_VISIBLE_DEVICES": "quay.io/ramalama/musa",
    })
    api: str = "none"
    keep_groups: bool = False
    ngl: int = -1
    threads: int = -1
    nocontainer: bool = False
    port: str = str(DEFAULT_PORT)
    pull: str = "newer"
    runtime: str = "llama.cpp"
    store: str = field(default_factory=get_store)
    temp: str = "0.8"
    transport: str = "ollama"
    use_model_store: bool = True
    ocr: bool = False
    default_image: str = DEFAULT_IMAGE


class ConfigLoader:
    @staticmethod
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
            if os.path.isdir(path + ".d"):
                for conf_file in sorted(Path(path + ".d").glob("*.conf")):
                    config = parser.parse_file(conf_file)

 
        return config.get("ramalama", {})

    @staticmethod
    def load_env_config(env: dict | None = None) -> dict[str, Any]:
        if env is None:
            env = os.environ
        envvars = {
            'container': 'RAMALAMA_IN_CONTAINER',
            'engine': 'RAMALAMA_CONTAINER_ENGINE',
            'image': 'RAMALAMA_IMAGE',
            'store': 'RAMALAMA_STORE',
            'transport': 'RAMALAMA_TRANSPORT',
        }
        config = {k: value for k, v in envvars.items() if (value := env.get(v)) is not None}
        return config

    @staticmethod
    def load() -> Config:
        file_config = ConfigLoader.load_file_config()
        env_config = ConfigLoader.load_env_config()

        # env variables take precedence over file config
        return Config(**(file_config | env_config))


CONFIG = ConfigLoader.load()
