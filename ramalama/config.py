import os
from collections import ChainMap
from pathlib import Path
from typing import Any, Dict

from ramalama.common import container_manager, default_image
from ramalama.toml_parser import TOMLParser

DEFAULT_PORT_RANGE = (8080, 8090)
DEFAULT_PORT = DEFAULT_PORT_RANGE[0]


def get_store():
    if os.geteuid() == 0:
        return "/var/lib/ramalama"

    return os.path.expanduser("~/.local/share/ramalama")


def use_container():
    use_container = os.getenv("RAMALAMA_IN_CONTAINER")
    if use_container:
        return use_container.lower() == "true"

    conman = container_manager()
    return conman is not None


def load_config() -> Dict[str, Any]:
    """Load configuration from a list of paths, in priority order."""
    parser = TOMLParser()
    config_path = os.getenv("RAMALAMA_CONFIG")
    if config_path:
        return parser.parse_file(config_path)

    config = {}
    config_paths = [
        "/usr/share/ramalama/ramalama.conf",
        "/usr/local/share/ramalama/ramalama.conf",
        "/etc/ramalama/ramalama.conf",
    ]
    config_home = os.getenv("XDG_CONFIG_HOME", os.path.join("~", ".config"))
    config_paths.extend([os.path.expanduser(os.path.join(config_home, "ramalama", "ramalama.conf"))])

    # Load configuration from each path
    for path in config_paths:
        if os.path.exists(path):
            # Load the main config file
            config = parser.parse_file(path)
        if os.path.isdir(path + ".d"):
            # Load all .conf files in ramalama.conf.d directory
            for conf_file in sorted(Path(path + ".d").glob("*.conf")):
                config = parser.parse_file(conf_file)

    return config


def load_config_from_env(config: Dict[str, Any], env: Dict):
    """Load configuration from environment variables."""
    envvars = {
        'container': 'RAMALAMA_IN_CONTAINER',
        'engine': 'RAMALAMA_CONTAINER_ENGINE',
        'image': 'RAMALAMA_IMAGE',
        'store': 'RAMALAMA_STORE',
        'transport': 'RAMALAMA_TRANSPORT',
    }
    for k, v in envvars.items():
        if value := env.get(v):
            config[k] = value


def load_config_defaults(config: Dict[str, Any]):
    """Set configuration defaults if these are not yet set."""
    config.setdefault('carimage', "registry.access.redhat.com/ubi9-micro:latest")
    config.setdefault('container', use_container())
    config.setdefault('ctx_size', 2048)
    config.setdefault('engine', container_manager())
    config.setdefault('env', [])
    config.setdefault('host', "0.0.0.0")
    config.setdefault('image', default_image())
    config.setdefault(
        'images',
        {
            "ASAHI_VISIBLE_DEVICES": "quay.io/ramalama/asahi",
            "ASCEND_VISIBLE_DEVICES": "quay.io/ramalama/cann",
            "CUDA_VISIBLE_DEVICES": "quay.io/ramalama/cuda",
            "HIP_VISIBLE_DEVICES": "quay.io/ramalama/rocm",
            "INTEL_VISIBLE_DEVICES": "quay.io/ramalama/intel-gpu",
            "MUSA_VISIBLE_DEVICES": "quay.io/ramalama/musa",
        },
    )
    config.setdefault('api', 'none')
    config.setdefault('keep_groups', False)
    config.setdefault('ngl', -1)
    config.setdefault('threads', -1)
    config.setdefault('nocontainer', False)
    config.setdefault('port', str(DEFAULT_PORT))
    config.setdefault('pull', "newer")
    config.setdefault('runtime', 'llama.cpp')
    config.setdefault('store', get_store())
    config.setdefault('temp', "0.8")
    config.setdefault('transport', "ollama")
    config.setdefault('use_model_store', True)
    config.setdefault('ocr', False)


class Config(ChainMap):
    def __init__(self, from_env, from_file, default):
        super().__init__(from_env, from_file, default)

    @property
    def from_env(self):
        return self.maps[0]

    @property
    def from_file(self):
        return self.maps[1]

    @property
    def default(self):
        return self.maps[2]

    def is_set(self, key):
        if key in self.from_env:
            return True
        if key in self.from_file:
            return True
        return False


def load_and_merge_config() -> Dict[str, Any]:
    """Load configuration from files, merge with environment variables and set defaults for options not set."""
    config = load_config()

    ramalama_config = config.setdefault('ramalama', {})

    env_config = {}
    load_config_from_env(env_config, os.environ)

    default_config = {}
    load_config_defaults(default_config)

    return Config(env_config, ramalama_config, default_config)


CONFIG = load_and_merge_config()
