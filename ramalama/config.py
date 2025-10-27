import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, TypeAlias

from ramalama.cli_arg_normalization import normalize_pull_arg
from ramalama.common import apple_vm, available
from ramalama.layered_config import LayeredMixin
from ramalama.toml_parser import TOMLParser

PathStr: TypeAlias = str
DEFAULT_PORT_RANGE: tuple[int, int] = (8080, 8090)
DEFAULT_PORT: int = DEFAULT_PORT_RANGE[0]
DEFAULT_IMAGE: str = "quay.io/ramalama/ramalama"
DEFAULT_STACK_IMAGE: str = "quay.io/ramalama/llama-stack"
DEFAULT_RAG_IMAGE: str = "quay.io/ramalama/ramalama-rag"
SUPPORTED_ENGINES: TypeAlias = Literal["podman", "docker"]
SUPPORTED_RUNTIMES: TypeAlias = Literal["llama.cpp", "vllm", "mlx"]
COLOR_OPTIONS: TypeAlias = Literal["auto", "always", "never"]
GGUF_QUANTIZATION_MODES: TypeAlias = Literal[
    "Q2_K",
    "Q3_K_S",
    "Q3_K_M",
    "Q3_K_L",
    "Q4_0",
    "Q4_K_S",
    "Q4_K_M",
    "Q5_0",
    "Q5_K_S",
    "Q5_K_M",
    "Q6_K",
    "Q8_0",
]
DEFAULT_GGUF_QUANTIZATION_MODE = "Q4_K_M"

DEFAULT_CONFIG_DIRS = [
    Path(f"{sys.prefix}/share/ramalama"),
    Path(f"{sys.prefix}/local/share/ramalama"),
    Path("/etc/ramalama"),
    Path(os.path.expanduser(os.path.join(os.getenv("XDG_DATA_HOME", "~/.local/share"), "ramalama"))),
    Path(os.path.expanduser(os.path.join(os.getenv("XDG_CONFIG_HOME", "~/.config"), "ramalama"))),
]


def get_default_engine() -> SUPPORTED_ENGINES | None:
    """Determine the container manager to use based on environment and platform."""
    if os.path.exists("/run/.toolboxenv"):
        return None

    if available("podman"):
        return "podman"

    return "docker" if available("docker") else None


def get_default_store() -> str:
    if os.geteuid() == 0:
        return "/var/lib/ramalama"

    return os.path.expanduser("~/.local/share/ramalama")


def get_all_inference_spec_dirs(subdir: str) -> list[Path]:
    ramalama_root = Path(__file__).parent.parent
    development_spec_dir = ramalama_root / "inference-spec" / subdir
    all_dirs = [development_spec_dir, *[conf_dir / "inference" for conf_dir in DEFAULT_CONFIG_DIRS]]

    return [d for d in all_dirs if d.exists()]


def get_inference_spec_files() -> dict[str, Path]:
    files: dict[str, Path] = {}

    for spec_dir in get_all_inference_spec_dirs("engines"):

        # Give preference to .yaml, then .json spec files
        file_extensions = ["*.yaml", "*.yml", "*.json"]
        for file_extension in file_extensions:
            # On naming collisions, i.e. muliple specs for one inference engine, prefer the
            # spec files discovered later (i.e. user-level > system-level)
            for spec_file in sorted(Path(spec_dir).glob(file_extension)):
                file = Path(spec_file)
                runtime = file.stem
                files[runtime] = file

    return files


def get_inference_schema_files() -> dict[str, Path]:
    files: dict[str, Path] = {}

    for schema_dir in get_all_inference_spec_dirs("schema"):

        for spec_file in sorted(Path(schema_dir).glob("schema.*.json")):
            file = Path(spec_file)
            version = file.name.replace("schema.", "").replace(".json", "")
            files[version] = file

    return files


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

    config_files: list[str] | None = None


@dataclass
class BaseConfig:
    api: str = "none"
    api_key: str = None
    cache_reuse: int = 256
    carimage: str = "registry.access.redhat.com/ubi10-micro:latest"
    container: bool = None  # type: ignore
    ctx_size: int = 0
    default_image: str = DEFAULT_IMAGE
    default_rag_image: str = DEFAULT_RAG_IMAGE
    dryrun: bool = False
    engine: SUPPORTED_ENGINES | None = field(default_factory=get_default_engine)
    env: list[str] = field(default_factory=list)
    host: str = "0.0.0.0"
    image: str = None  # type: ignore
    images: dict[str, str] = field(
        default_factory=lambda: {
            "ASAHI_VISIBLE_DEVICES": "quay.io/ramalama/asahi",
            "ASCEND_VISIBLE_DEVICES": "quay.io/ramalama/cann",
            "CUDA_VISIBLE_DEVICES": "quay.io/ramalama/cuda",
            "GGML_VK_VISIBLE_DEVICES": "quay.io/ramalama/ramalama",
            "HIP_VISIBLE_DEVICES": "quay.io/ramalama/rocm",
            "INTEL_VISIBLE_DEVICES": "quay.io/ramalama/intel-gpu",
            "MUSA_VISIBLE_DEVICES": "quay.io/ramalama/musa",
            "VLLM": "registry.redhat.io/rhelai1/ramalama-vllm",
        }
    )
    rag_image: str | None = None
    rag_images: dict[str, str] = field(
        default_factory=lambda: {
            "CUDA_VISIBLE_DEVICES": "quay.io/ramalama/cuda-rag",
            "HIP_VISIBLE_DEVICES": "quay.io/ramalama/rocm-rag",
            "INTEL_VISIBLE_DEVICES": "quay.io/ramalama/intel-gpu-rag",
        }
    )
    keep_groups: bool = False
    max_tokens: int = 0
    ngl: int = -1
    ocr: bool = False
    port: str = str(DEFAULT_PORT)
    prefix: str = None  # type: ignore
    pull: str = "newer"
    rag_format: Literal["qdrant", "json", "markdown", "milvus"] = "qdrant"
    runtime: SUPPORTED_RUNTIMES = "llama.cpp"
    selinux: bool = False
    settings: RamalamaSettings = field(default_factory=RamalamaSettings)
    stack_image: str = DEFAULT_STACK_IMAGE
    store: str = field(default_factory=get_default_store)
    temp: str = "0.8"
    thinking: bool = True
    threads: int = -1
    transport: str = "ollama"
    user: UserConfig = field(default_factory=UserConfig)
    verify: bool = True
    gguf_quantization_mode: GGUF_QUANTIZATION_MODES = DEFAULT_GGUF_QUANTIZATION_MODE

    def __post_init__(self):
        self.container = coerce_to_bool(self.container) if self.container is not None else self.engine is not None
        self.image = self.image if self.image is not None else self.default_image
        self.pull = normalize_pull_arg(self.pull, self.engine)


class Config(LayeredMixin, BaseConfig):
    """
    Config class that combines multiple configuration layers to create a complete BaseConfig.
    Exposes the same attributes as BaseConfig, but allows for dynamic loading of configuration layers.
    Mixins should be inherited first.
    """

    def __post_init__(self):
        self._finalize_engine()
        super().__post_init__()

    def _finalize_engine(self: "Config"):
        """
        Finalizes engine selection, with special handling for Podman on macOS.

        If Podman is detected on macOS without a configured machine, it falls back on docker availability.
        """
        is_podman = self.engine is not None and os.path.basename(self.engine) == "podman"
        if is_podman and sys.platform == "darwin":
            run_with_podman_engine = apple_vm(self.engine, self)
            if not run_with_podman_engine and not self.is_set("engine"):
                self.engine = "docker" if available("docker") else None


def load_file_config() -> dict[str, Any]:
    parser = TOMLParser()
    config_path = os.getenv("RAMALAMA_CONFIG")

    if config_path and os.path.exists(config_path):
        config = parser.parse_file(config_path)
        config = config.get("ramalama", {})
        config['settings'] = {'config_files': [config_path]}
        return config

    config = {}
    default_config_paths = [os.path.join(conf_dir, "ramalama.conf") for conf_dir in DEFAULT_CONFIG_DIRS]

    config_paths = []
    for path in default_config_paths:
        if os.path.exists(path):
            config_paths.append(str(path))
            parser.parse_file(path)
        path_str = f"{path}.d"
        if os.path.isdir(path_str):
            for conf_file in sorted(Path(path_str).glob("*.conf")):
                config_paths.append(str(conf_file))
                parser.parse_file(conf_file)
    config = parser.data
    if config:
        config = config.get('ramalama', {})
        config['settings'] = {'config_files': config_paths}
    return config


def load_env_config(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    if env is None:
        env = os.environ

    config: dict[str, Any] = {}
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

    for key in ['images', 'rag_images']:
        if key in config:
            config[key] = json.loads(config[key])

    for key in ['ocr', 'keep_groups', 'container', 'verify']:
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
