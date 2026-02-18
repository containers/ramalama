from typing import Literal, TypeAlias

PathStr: TypeAlias = str
SUPPORTED_ENGINES: TypeAlias = Literal["podman", "docker"]
SUPPORTED_RUNTIMES: TypeAlias = Literal["llama.cpp", "vllm", "mlx", "whisper.cpp"]
COLOR_OPTIONS: TypeAlias = Literal["auto", "always", "never"]
