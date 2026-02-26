import json
import os
import sys
from dataclasses import dataclass, field, fields
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Mapping, TypeAlias

from ramalama.cli_arg_normalization import normalize_pull_arg
from ramalama.common import apple_vm, available
from ramalama.config_types import SUPPORTED_ENGINES, SUPPORTED_RUNTIMES
from ramalama.layered_config import LayeredMixin
from ramalama.log_levels import LogLevel, coerce_log_level
from ramalama.toml_parser import TOMLParser

DEFAULT_IMAGE: str = "quay.io/ramalama/ramalama"
DEFAULT_STACK_IMAGE: str = "quay.io/ramalama/llama-stack"
DEFAULT_RAG_IMAGE: str = "quay.io/ramalama/ramalama-rag"
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
DEFAULT_GGUF_QUANTIZATION_MODE: GGUF_QUANTIZATION_MODES = "Q4_K_M"


def _get_default_config_dirs() -> list[Path]:
    """Get platform-appropriate config directories."""
    dirs = [
        Path(f"{sys.prefix}/share/ramalama"),
        Path(f"{sys.prefix}/local/share/ramalama"),
    ]

    if os.name == 'nt':
        # Windows-specific paths using APPDATA and LOCALAPPDATA
        appdata = os.getenv("APPDATA", os.path.expanduser("~/AppData/Roaming"))
        localappdata = os.getenv("LOCALAPPDATA", os.path.expanduser("~/AppData/Local"))
        dirs.extend(
            [
                Path(os.path.join(localappdata, "ramalama")),
                Path(os.path.join(appdata, "ramalama")),
            ]
        )
    else:
        # Unix-specific paths
        dirs.extend(
            [
                Path("/etc/ramalama"),
                Path(os.path.expanduser(os.path.join(os.getenv("XDG_DATA_HOME", "~/.local/share"), "ramalama"))),
                Path(os.path.expanduser(os.path.join(os.getenv("XDG_CONFIG_HOME", "~/.config"), "ramalama"))),
            ]
        )

    return dirs


DEFAULT_CONFIG_DIRS = _get_default_config_dirs()


def get_default_engine() -> SUPPORTED_ENGINES | None:
    """Determine the container manager to use based on environment and platform."""
    if os.path.exists("/run/.toolboxenv"):
        return None

    if available("podman"):
        return "podman"

    return "docker" if available("docker") else None


@lru_cache(maxsize=1)
def get_default_store() -> str:
    # Check if running as root (Unix only)
    if hasattr(os, 'geteuid') and os.geteuid() == 0:
        return "/var/lib/ramalama"

    return os.path.expanduser(os.path.join(os.getenv("XDG_DATA_HOME", "~/.local/share"), "ramalama"))


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


def get_storage_folder(base_path: str | None = None):
    if base_path is None:
        base_path = get_default_store()

    return os.path.join(base_path, "benchmarks")


@dataclass
class Benchmarks:
    storage_folder: str = field(default_factory=get_storage_folder)
    disable: bool = False

    def __post_init__(self):
        os.makedirs(self.storage_folder, exist_ok=True)


@dataclass
class UserConfig:
    no_missing_gpu_prompt: bool = False

    def __post_init__(self):
        self.no_missing_gpu_prompt = coerce_to_bool(self.no_missing_gpu_prompt)


@dataclass
class OpenaiProviderConfig:
    api_key: str | None = None


@dataclass
class ProviderConfig:
    openai: OpenaiProviderConfig = field(default_factory=OpenaiProviderConfig)


@dataclass
class RamalamaSettings:
    """These settings are not managed directly by the user"""

    config_files: list[str] | None = None


@dataclass
class RamalamaImageConfig:
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any):
        setattr(self, key, value)

    def __contains__(self, key: str) -> bool:
        return key in {f.name for f in fields(self)}

    def __iter__(self):
        return iter(f.name for f in fields(self))

    def __len__(self) -> int:
        return len(fields(self))


@dataclass
class RamalamaImages(RamalamaImageConfig):
    ASAHI_VISIBLE_DEVICES: str = "quay.io/ramalama/asahi"
    ASCEND_VISIBLE_DEVICES: str = "quay.io/ramalama/cann"
    CUDA_VISIBLE_DEVICES: str = "quay.io/ramalama/cuda"
    GGML_VK_VISIBLE_DEVICES: str = "quay.io/ramalama/ramalama"
    HIP_VISIBLE_DEVICES: str = "quay.io/ramalama/rocm"
    INTEL_VISIBLE_DEVICES: str = "quay.io/ramalama/intel-gpu"
    MUSA_VISIBLE_DEVICES: str = "quay.io/ramalama/musa"
    VLLM_ASAHI_VISIBLE_DEVICES: str = "docker.io/vllm/vllm-openai"
    VLLM_ASCEND_VISIBLE_DEVICES: str = "docker.io/vllm/vllm-openai"
    VLLM_CUDA_VISIBLE_DEVICES: str = "docker.io/vllm/vllm-openai"
    VLLM_GGML_VK_VISIBLE_DEVICES: str = "docker.io/vllm/vllm-openai"
    VLLM_HIP_VISIBLE_DEVICES: str = "docker.io/vllm/vllm-openai"
    VLLM_INTEL_VISIBLE_DEVICES: str = "docker.io/vllm/vllm-openai"
    VLLM_MUSA_VISIBLE_DEVICES: str = "docker.io/vllm/vllm-openai"


@dataclass
class RamalamaRagImages(RamalamaImageConfig):
    CUDA_VISIBLE_DEVICES: str = "quay.io/ramalama/cuda-rag"
    HIP_VISIBLE_DEVICES: str = "quay.io/ramalama/rocm-rag"
    INTEL_VISIBLE_DEVICES: str = "quay.io/ramalama/intel-gpu-rag"


@dataclass
class HTTPClientConfig:
    max_retries: int = 5
    max_retry_delay: int = 30

    def __post_init__(self):
        self.max_retries = int(self.max_retries)
        if self.max_retries < 0:
            raise ValueError(f"http_client.max_retries must be non-negative: {self.max_retries}")
        self.max_retry_delay = int(self.max_retry_delay)
        if self.max_retry_delay < 0:
            raise ValueError(f"http_client.max_retry_delay must be non-negative: {self.max_retry_delay}")


@dataclass
class BaseConfig:
    api: str = "none"
    api_key: str | None = None
    benchmarks: Benchmarks = field(default_factory=Benchmarks)
    cache_reuse: int = 256
    carimage: str = "registry.access.redhat.com/ubi10-micro:latest"
    container: bool = None  # type: ignore
    ctx_size: int = 0
    convert_type: Literal["artifact", "car", "raw"] = "raw"
    default_image: str = DEFAULT_IMAGE
    default_rag_image: str = DEFAULT_RAG_IMAGE
    dryrun: bool = False
    engine: SUPPORTED_ENGINES | None = field(default_factory=get_default_engine)
    env: list[str] = field(default_factory=list)
    gguf_quantization_mode: GGUF_QUANTIZATION_MODES = DEFAULT_GGUF_QUANTIZATION_MODE
    host: str = "0.0.0.0"
    http_client: HTTPClientConfig = field(default_factory=HTTPClientConfig)
    image: str = None  # type: ignore
    images: RamalamaImages = field(default_factory=RamalamaImages)
    rag_image: str | None = None
    rag_images: RamalamaRagImages = field(default_factory=RamalamaRagImages)
    keep_groups: bool = False
    log_level: LogLevel | None = None
    max_tokens: int = 0
    ngl: int = -1
    ocr: bool = False
    port: str = "8080"
    prefix: str = None  # type: ignore
    pull: str = "newer"
    rag_format: Literal["qdrant", "json", "markdown", "milvus"] = "qdrant"
    runtime: SUPPORTED_RUNTIMES = "llama.cpp"
    selinux: bool = False
    settings: RamalamaSettings = field(default_factory=RamalamaSettings)
    stack_image: str = DEFAULT_STACK_IMAGE
    store: str = field(default_factory=get_default_store)
    summarize_after: int = 4
    temp: str = "0.8"
    thinking: bool = True
    threads: int = -1
    transport: str = "ollama"
    user: UserConfig = field(default_factory=UserConfig)
    verify: bool = True
    provider: ProviderConfig = field(default_factory=ProviderConfig)

    def __post_init__(self):
        self.container = coerce_to_bool(self.container) if self.container is not None else self.engine is not None
        self.image = self.image if self.image is not None else self.default_image
        self.pull = normalize_pull_arg(self.pull, self.engine)
        self.log_level = coerce_log_level(self.log_level) if self.log_level is not None else self.log_level

    @property
    def default_port_range(self) -> tuple[int, int]:
        port = int(self.port)
        return (port, port + 100)


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
        if self.engine is not None and os.path.basename(self.engine) == "podman" and sys.platform == "darwin":
            run_with_podman_engine = apple_vm(self.engine, self)
            if not run_with_podman_engine and not self.is_set("engine"):
                self.engine = "docker" if available("docker") else None


def load_file_config() -> dict[str, Any]:
    parser = TOMLParser()
    config_paths: list[str] = []

    if (config_path := os.getenv("RAMALAMA_CONFIG", None)) and os.path.exists(config_path):
        config_paths.append(config_path)
    else:
        default_config_paths = [os.path.join(conf_dir, "ramalama.conf") for conf_dir in DEFAULT_CONFIG_DIRS]

        for path in default_config_paths:
            if os.path.exists(path):
                config_paths.append(str(path))

            path_str = f"{path}.d"
            if os.path.isdir(path_str):
                for conf_file in sorted(Path(path_str).glob("*.conf")):
                    config_paths.append(str(conf_file))

    for file in config_paths:
        parser.parse_file(file)

    config: dict[str, Any] = parser.data
    if config:
        config = config.get('ramalama', {})
        config['settings'] = {'config_files': config_paths}
        if log_level := config.get("log_level"):
            config["log_level"] = coerce_log_level(log_level)
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

    for key in ['threads', 'ctx_size', 'ngl', 'summarize_after']:
        if key in config:
            config[key] = int(config[key])
    if log_level := config.get("log_level"):
        config["log_level"] = coerce_log_level(log_level)
    return config


def default_config(env: Mapping[str, str] | None = None) -> Config:
    """Returns a default Config object with all layers initialized."""
    return Config(load_env_config(env), load_file_config())


@lru_cache(maxsize=1)
def get_config() -> Config:
    return default_config()
