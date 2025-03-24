import os
from pathlib import Path
from typing import Any, Dict

from ramalama.common import container_manager, default_image
from ramalama.toml_parser import TOMLParser

DEFAULT_PORT_RANGE = (8080, 8090)


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
    config['container'] = env.get('RAMALAMA_IN_CONTAINER', config.get('container', use_container()))
    config['engine'] = env.get('RAMALAMA_CONTAINER_ENGINE', config.get('engine', container_manager()))
    config['image'] = env.get('RAMALAMA_IMAGE', config.get('image', default_image()))
    config['store'] = env.get('RAMALAMA_STORE', config.get('store', get_store()))
    config['transport'] = env.get('RAMALAMA_TRANSPORT', config.get('transport', "ollama"))


def int_tuple_as_str(input: tuple) -> str:
    return '-'.join(map(str, input))


def load_config_defaults(config: Dict[str, Any]):
    """Set configuration defaults if these are not yet set."""
    config['carimage'] = config.get('carimage', "registry.access.redhat.com/ubi9-micro:latest")
    config['ctx_size'] = config.get('ctx_size', 2048)
    config['env'] = config.get('env', [])
    config['host'] = config.get('host', "0.0.0.0")
    config['keep_groups'] = config.get('keep_groups', False)
    config['ngl'] = config.get('ngl', -1)
    config['threads'] = config.get('threads', -1)
    config['nocontainer'] = config.get('nocontainer', False)
    config['port'] = config.get('port', int_tuple_as_str(DEFAULT_PORT_RANGE))
    config['pull'] = config.get('pull', "newer")
    config['runtime'] = config.get('runtime', 'llama.cpp')
    config['temp'] = config.get('temp', "0.8")
    config['use_model_store'] = config.get('use_model_store', False)
    config['images'] = config.get(
        'images',
        {
            "ASAHI_VISIBLE_DEVICES": "quay.io/ramalama/asahi",
            "ASCEND_VISIBLE_DEVICES": "quay.io/ramalama/cann",
            "CUDA_VISIBLE_DEVICES": "quay.io/ramalama/cuda",
            "HIP_VISIBLE_DEVICES": "quay.io/ramalama/rocm-fedora",
            "INTEL_VISIBLE_DEVICES": "quay.io/ramalama/intel-gpu",
        },
    )


def load_and_merge_config() -> Dict[str, Any]:
    """Load configuration from files, merge with environment variables and set defaults for options not set."""
    config = load_config()

    ramalama_config = config.setdefault('ramalama', {})
    load_config_from_env(ramalama_config, os.environ)
    load_config_defaults(ramalama_config)

    return ramalama_config


CONFIG = load_and_merge_config()
