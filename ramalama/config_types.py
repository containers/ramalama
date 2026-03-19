from typing import Literal, TypeAlias

PathStr: TypeAlias = str
SUPPORTED_ENGINES: TypeAlias = Literal["podman", "docker"]
SUPPORTED_RUNTIMES: TypeAlias = str
COLOR_OPTIONS: TypeAlias = Literal["auto", "always", "never"]
