from __future__ import annotations

from typing import Optional


def normalize_pull_arg(pull: str, engine: Optional[str]):
    return "always" if engine == "docker" and pull == "newer" else pull
