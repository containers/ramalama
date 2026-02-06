from typing import Literal, TypeAlias

PathStr: TypeAlias = str
SUPPORTED_ENGINES: TypeAlias = Literal["podman", "docker"]
SUPPORTED_RUNTIMES: TypeAlias = Literal["llama.cpp", "vllm", "mlx"]
COLOR_OPTIONS: TypeAlias = Literal["auto", "always", "never"]
