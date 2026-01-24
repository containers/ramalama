import os
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, List, Optional

from ramalama.common import engine_version, run_cmd

STRATEGY_AUTO = "auto"
STRATEGY_PODMAN_ARTIFACT = "podman-artifact"
STRATEGY_PODMAN_IMAGE = "podman-image"
STRATEGY_HTTP_BIND = "http-bind"

PODMAN_MIN_ARTIFACT_VERSION = "5.7.0"


def _parse_version(version: str) -> List[int]:
    parts = []
    for part in version.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return parts


def _version_gte(version: str, minimum: str) -> bool:
    v_parts = _parse_version(version)
    m_parts = _parse_version(minimum)
    # Normalize length
    while len(v_parts) < len(m_parts):
        v_parts.append(0)
    while len(m_parts) < len(v_parts):
        m_parts.append(0)
    return v_parts >= m_parts


def _artifact_supported(engine: str, version: str, runner: Optional[Callable] = None) -> bool:
    runner = runner or run_cmd
    if not _version_gte(version, PODMAN_MIN_ARTIFACT_VERSION):
        return False
    try:
        runner([engine, "artifact", "ls"], ignore_all=True)
        return True
    except Exception:
        return False


@dataclass
class ArtifactCapabilities:
    engine: Optional[str]
    is_podman: bool
    is_docker: bool
    version: Optional[str]
    artifact_supported: bool
    order: List[str]


def _compute_order(caps: ArtifactCapabilities) -> List[str]:
    if caps.artifact_supported:
        return [STRATEGY_PODMAN_ARTIFACT, STRATEGY_PODMAN_IMAGE, STRATEGY_HTTP_BIND]
    if caps.is_podman:
        return [STRATEGY_PODMAN_IMAGE, STRATEGY_HTTP_BIND]
    return [STRATEGY_HTTP_BIND]


@lru_cache(maxsize=None)
def probe_capabilities(engine: Optional[str]) -> ArtifactCapabilities:
    engine_name = os.path.basename(engine) if engine else ""
    is_podman = engine_name == "podman"
    is_docker = engine_name == "docker"
    version = None
    artifact = False

    if is_podman:
        try:
            version = engine_version(engine)
        except (FileNotFoundError, subprocess.CalledProcessError):
            version = None
        if version:
            artifact = _artifact_supported(engine, version, runner=run_cmd)

    caps = ArtifactCapabilities(
        engine=engine,
        is_podman=is_podman,
        is_docker=is_docker,
        version=version,
        artifact_supported=artifact,
        order=[],
    )
    caps.order = _compute_order(caps)
    return caps


def select_strategy(mode: str, caps: ArtifactCapabilities) -> str:
    if mode == STRATEGY_AUTO:
        return caps.order[0]

    if mode == STRATEGY_PODMAN_ARTIFACT and not caps.artifact_supported:
        raise ValueError("podman artifact strategy requested but engine does not support artifacts")
    if mode == STRATEGY_PODMAN_IMAGE and not caps.is_podman:
        raise ValueError("podman image strategy requested but engine is not podman")
    if mode == STRATEGY_HTTP_BIND:
        return mode

    if mode in {STRATEGY_PODMAN_ARTIFACT, STRATEGY_PODMAN_IMAGE}:
        return mode

    raise ValueError(f"unknown strategy '{mode}'")


def clear_probe_cache() -> None:
    probe_capabilities.cache_clear()
