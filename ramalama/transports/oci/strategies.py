import json
import os
from abc import ABC, abstractmethod
from typing import Generic, Literal, TypeVar

from ramalama.annotations import AnnotationFilepath, AnnotationTitle
from ramalama.common import MNT_DIR, run_cmd
from ramalama.model_store.store import ModelStore
from ramalama.path_utils import get_container_mount_path
from ramalama.transports.oci.oci_artifact import OCIRegistryClient, _split_reference, download_oci_artifact

StrategyKind = Literal["artifact", "image"]
K = TypeVar("K", bound=StrategyKind)


class BaseOCIStrategy(Generic[K], ABC):
    """Interface for artifact handling strategies."""

    kind: K
    model_store: ModelStore | None

    def __init__(self, *, model_store: ModelStore | None = None):
        self.model_store = model_store

    @abstractmethod
    def pull(self, ref: str, *args, **kwargs) -> None:
        raise NotImplementedError

    @abstractmethod
    def exists(self, *args, **kwargs) -> bool:
        raise NotImplementedError

    @abstractmethod
    def mount_arg(self, *args, **kwargs) -> str | None:
        """Return a mount argument for container run, or None if not applicable."""
        raise NotImplementedError

    @abstractmethod
    def remove(self, ref: str, *args, **kwargs) -> bool:
        raise NotImplementedError

    @abstractmethod
    def filenames(self, ref: str) -> list[str]:
        """Return the list of candidate model filenames."""
        raise NotImplementedError

    @abstractmethod
    def inspect(self, ref: str) -> str:
        """Return raw inspect output for the reference."""
        raise NotImplementedError

    def entrypoint_path(self, ref: str, mount_dir: str | None = None) -> str:
        mount_dir = mount_dir or MNT_DIR
        filenames = self.filenames(ref)
        if not filenames:
            raise ValueError(f"No model files found for {ref}")
        return os.path.join(mount_dir, filenames[0])


class BaseArtifactStrategy(BaseOCIStrategy[Literal['artifact']]):
    kind: Literal['artifact'] = "artifact"

    def __init__(self, engine: str, *, model_store: ModelStore):
        self.engine = engine
        self.model_store = model_store


class BaseImageStrategy(BaseOCIStrategy[Literal['image']]):
    kind: Literal['image'] = 'image'

    def __init__(self, engine: str, *, model_store: ModelStore):
        self.engine = engine
        self.model_store = model_store

    def pull(self, ref: str, cmd_args: list[str] = []) -> None:
        run_cmd([self.engine, "pull", ref, *cmd_args])

    def exists(self, src: str) -> bool:
        try:
            run_cmd([self.engine, "image", "inspect", src], ignore_stderr=True)
            return True
        except Exception:
            return False

    def remove(self, ref: str, cmd_args: list[str] = []) -> bool:
        try:
            run_cmd([self.engine, "manifest", "rm", ref], ignore_stderr=True)
            return True
        except Exception:
            pass
        try:
            run_cmd([self.engine, "image", "rm", *cmd_args, ref], ignore_stderr=True)
            return True
        except Exception:
            return False

    def filenames(self, ref: str) -> list[str]:
        return ["model.file"]

    def inspect(self, ref: str) -> str:
        result = run_cmd([self.engine, "image", "inspect", ref], ignore_stderr=True)
        return result.stdout.decode("utf-8").strip()


def normalize_reference(reference: str) -> str:
    if "://" in reference:
        return reference.split("://", 1)[1]
    return reference


def split_oci_reference(reference: str) -> tuple[str, str]:
    normalized = normalize_reference(reference)
    if "/" not in normalized:
        raise KeyError(
            "You must specify a registry for the model in the form "
            f"'oci://registry.acme.org/ns/repo:tag', got instead: {reference}"
        )
    registry, ref = normalized.split("/", 1)
    return registry, ref


def model_tag_from_ref(reference: str) -> str:
    _, ref = split_oci_reference(reference)
    if "@" in ref:
        return ref.split("@", 1)[1]
    if ":" in ref.rsplit("/", 1)[-1]:
        return ref.rsplit(":", 1)[1]
    return "latest"


class HttpArtifactStrategy(BaseArtifactStrategy):
    """HTTP download + bind mount strategy (used for Docker or fallback)."""

    def __init__(self, engine: str = "podman", *, model_store: ModelStore):
        super().__init__(engine=engine, model_store=model_store)

    def pull(self, ref: str, cmd_args: list[str] = []) -> None:
        if not self.model_store:
            raise ValueError("HTTP artifact strategy requires a model store")
        registry, reference = split_oci_reference(ref)
        model_tag = model_tag_from_ref(ref)
        download_oci_artifact(
            registry=registry,
            reference=reference,
            model_store=self.model_store,
            model_tag=model_tag,
        )

    def exists(self, src: str) -> bool:
        if not self.model_store:
            return False
        try:
            model_tag = model_tag_from_ref(src)
            _, cached_files, complete = self.model_store.get_cached_files(model_tag)
            return complete and bool(cached_files)
        except Exception:
            return False

    def remove(self, ref: str, cmd_args: list[str] = []) -> bool:
        if not self.model_store:
            return False
        try:
            model_tag = model_tag_from_ref(ref)
            return self.model_store.remove_snapshot(model_tag)
        except Exception:
            return False

    def mount_arg(self, src: str, dest: str | None = None) -> str | None:
        if not self.model_store:
            return None
        model_tag = model_tag_from_ref(src)
        snapshot_dir = self.model_store.get_snapshot_directory_from_tag(model_tag)
        container_path = get_container_mount_path(snapshot_dir)

        # TODO: SElinux
        relabel = getattr(self, "relabel", "")
        return f"--mount=type=bind,src={container_path},destination={dest or MNT_DIR},ro{relabel}"

    def filenames(self, ref: str) -> list[str]:
        if not self.model_store:
            raise ValueError("HTTP artifact strategy requires a model store")
        model_tag = model_tag_from_ref(ref)
        ref_file = self.model_store.get_ref_file(model_tag)
        if ref_file is None or not ref_file.model_files:
            raise ValueError(f"No model files found for artifact {ref}")
        return sorted(file.name for file in ref_file.model_files)

    def inspect(self, ref: str) -> str:
        registry, reference = split_oci_reference(ref)
        repository, ref_tag = _split_reference(reference)
        client = OCIRegistryClient(registry, repository, ref_tag)
        manifest, _ = client.get_manifest()
        return json.dumps(manifest)


class PodmanArtifactStrategy(BaseArtifactStrategy):
    def __init__(self, engine: str = "podman", *, model_store: ModelStore):
        super().__init__(engine=engine, model_store=model_store)

    def pull(self, ref: str, cmd_args: list[str] = []) -> None:
        run_cmd([self.engine, "artifact", "pull", ref, *cmd_args])

    def exists(self, src: str) -> bool:
        try:
            run_cmd([self.engine, "artifact", "inspect", src], ignore_stderr=True)
            return True
        except Exception:
            return False

    def mount_arg(self, src: str, dest: str | None = None) -> str:
        return f"--mount=type=artifact,src={src},destination={dest or MNT_DIR}"

    def remove(self, ref: str, cmd_args: list[str] = []) -> bool:
        try:
            run_cmd([self.engine, "artifact", "rm", *cmd_args, ref], ignore_stderr=True)
            return True
        except Exception:
            return False

    def filenames(self, ref: str) -> list[str]:
        result = run_cmd(
            [self.engine, "artifact", "inspect", "--format", "{{json .Manifest}}", ref],
            ignore_stderr=True,
        )

        payload = result.stdout.decode("utf-8").strip()
        manifest = json.loads(payload) if payload else {}
        names = []
        annotation_keys = [AnnotationFilepath, AnnotationTitle]
        for layer in manifest.get("layers") or manifest.get("blobs") or []:
            annotations = layer.get("annotations") or {}
            for annotation_key in annotation_keys:
                if name := annotations.get(annotation_key):
                    names.append(os.path.basename(name))
                    break

        if not names:
            raise ValueError(f"No layer filename annotations found for {ref}")

        return sorted(names)

    def entrypoint_path(self, ref: str, mount_dir: str | None = None) -> str:
        mount_dir = mount_dir or MNT_DIR
        filenames = self.filenames(ref)
        if not filenames:
            raise ValueError(f"No model files found for {ref}")
        if len(filenames) == 1:
            return mount_dir
        return os.path.join(mount_dir, filenames[0])

    def inspect(self, ref: str) -> str:
        result = run_cmd([self.engine, "artifact", "inspect", ref], ignore_stderr=True)
        return result.stdout.decode("utf-8").strip()


class PodmanImageStrategy(BaseImageStrategy):
    def __init__(self, engine: str = "podman", *, model_store: ModelStore):
        super().__init__(engine=engine, model_store=model_store)

    def mount_arg(self, src: str, dest: str | None = None) -> str:
        return f"--mount=type=image,src={src},destination={dest or MNT_DIR},subpath=/models,rw=false"


class DockerImageStrategy(BaseImageStrategy):
    def __init__(self, engine: str = "docker", *, model_store: ModelStore):
        super().__init__(engine=engine, model_store=model_store)

    def mount_arg(self, src: str, dest: str | None = None) -> str | None:
        return f"--mount=type=volume,src={src},dst={dest or MNT_DIR},readonly"
