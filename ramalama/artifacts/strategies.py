from dataclasses import dataclass
from typing import Callable, Optional

from ramalama.common import MNT_DIR, run_cmd


class ArtifactStrategy:
    """Interface for artifact handling strategies."""

    def pull(self) -> None:
        raise NotImplementedError

    def exists(self) -> bool:
        raise NotImplementedError

    def mount_arg(self) -> Optional[str]:
        """Return a mount argument for container run, or None if not applicable."""
        raise NotImplementedError


@dataclass
class PodmanArtifactStrategy(ArtifactStrategy):
    engine: str
    reference: str
    runner: Callable = run_cmd

    def pull(self) -> None:
        self.runner([self.engine, "artifact", "pull", self.reference])

    def exists(self) -> bool:
        try:
            self.runner([self.engine, "artifact", "inspect", self.reference], ignore_stderr=True)
            return True
        except Exception:
            return False

    def mount_arg(self) -> str:
        return f"--mount=type=artifact,src={self.reference},destination={MNT_DIR}"


@dataclass
class PodmanImageStrategy(ArtifactStrategy):
    engine: str
    reference: str
    runner: Callable = run_cmd

    def pull(self) -> None:
        self.runner([self.engine, "pull", self.reference])

    def exists(self) -> bool:
        try:
            self.runner([self.engine, "image", "inspect", self.reference], ignore_stderr=True)
            return True
        except Exception:
            return False

    def mount_arg(self) -> str:
        return f"--mount=type=image,src={self.reference},destination={MNT_DIR},subpath=/models,rw=false"


@dataclass
class HttpBindStrategy(ArtifactStrategy):
    """HTTP download + bind mount strategy (used for Docker or fallback)."""

    reference: str
    fetcher: Callable

    def pull(self) -> None:
        # Fetcher is responsible for downloading to local store
        self.fetcher(self.reference)

    def exists(self) -> bool:
        # Assume fetcher can act as existence check if it raises on missing
        try:
            self.fetcher(self.reference, check_only=True)
            return True
        except Exception:
            return False

    def mount_arg(self) -> Optional[str]:
        # Bind mounts are assembled elsewhere (per-file), so no single mount arg.
        return None
