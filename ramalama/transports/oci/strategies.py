import json
import os
import posixpath
from abc import ABC, abstractmethod
from typing import Generic, Literal, TypeVar

from ramalama.common import MNT_DIR, run_cmd
from ramalama.model_store.store import ModelStore
from ramalama.oci_tools import OciRef
from ramalama.path_utils import get_container_mount_path
from ramalama.transports.oci import spec as oci_spec
from ramalama.transports.oci.oci_artifact import OCIRegistryClient, download_oci_artifact

StrategyKind = Literal["artifact", "image"]
K = TypeVar("K", bound=StrategyKind)


class BaseOCIStrategy(Generic[K], ABC):
    """Interface for artifact handling strategies."""

    kind: K
    model_store: ModelStore | None

    def __init__(self, *, model_store: ModelStore | None = None):
        self.model_store = model_store

    @abstractmethod
    def pull(self, ref: OciRef, *args, **kwargs) -> None:
        raise NotImplementedError

    @abstractmethod
    def exists(self, ref: OciRef, *args, **kwargs) -> bool:
        raise NotImplementedError

    @abstractmethod
    def mount_arg(self, ref: OciRef, *args, **kwargs) -> str | None:
        """Return a mount argument for container run, or None if not applicable."""
        raise NotImplementedError

    @abstractmethod
    def remove(self, ref: OciRef, *args, **kwargs) -> bool:
        raise NotImplementedError

    @abstractmethod
    def filenames(self, ref: OciRef) -> list[str]:
        """Return the list of candidate model filenames."""
        raise NotImplementedError

    @abstractmethod
    def inspect(self, ref: OciRef) -> str:
        """Return raw inspect output for the reference."""
        raise NotImplementedError

    def entrypoint_path(self, ref: OciRef, mount_dir: str | None = None) -> str:
        mount_dir = mount_dir or MNT_DIR
        filenames = self.filenames(ref)
        if not filenames:
            raise ValueError(f"No model files found for {ref}")
        return posixpath.join(mount_dir, filenames[0])


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

    def pull(self, ref: OciRef, cmd_args: list[str] | None = None) -> None:
        if cmd_args is None:
            cmd_args = []
        run_cmd([self.engine, "pull", *cmd_args, str(ref)])

    def exists(self, ref: OciRef) -> bool:
        try:
            run_cmd([self.engine, "image", "inspect", str(ref)], ignore_stderr=True)
            return True
        except Exception:
            return False

    def remove(self, ref: OciRef, cmd_args: list[str] | None = None) -> bool:
        if cmd_args is None:
            cmd_args = []

        try:
            run_cmd([self.engine, "manifest", "rm", str(ref)], ignore_stderr=True)
            return True
        except Exception:
            pass
        try:
            run_cmd([self.engine, "image", "rm", *cmd_args, str(ref)], ignore_stderr=True)
            return True
        except Exception:
            return False

    def filenames(self, ref: OciRef) -> list[str]:
        return ["model.file"]

    def inspect(self, ref: OciRef) -> str:
        result = run_cmd([self.engine, "image", "inspect", str(ref)], ignore_stderr=True)
        return result.stdout.decode("utf-8").strip()


class HttpArtifactStrategy(BaseArtifactStrategy):
    """HTTP download + bind mount strategy (used for Docker or fallback)."""

    def __init__(self, engine: str = "podman", *, model_store: ModelStore):
        super().__init__(engine=engine, model_store=model_store)

    def pull(self, ref: OciRef, cmd_args: list[str] | None = None) -> None:
        if cmd_args is None:
            cmd_args = []
        if not self.model_store:
            raise ValueError("HTTP artifact strategy requires a model store")

        model_tag = ref.specifier
        download_oci_artifact(
            reference=str(ref),
            model_store=self.model_store,
            model_tag=model_tag,
        )

    def exists(self, ref: OciRef) -> bool:
        if not self.model_store:
            return False
        try:
            _, cached_files, complete = self.model_store.get_cached_files(ref.specifier)
            return complete and bool(cached_files)
        except Exception:
            return False

    def remove(self, ref: OciRef, cmd_args: list[str] | None = None) -> bool:
        if cmd_args is None:
            cmd_args = []

        if not self.model_store:
            return False
        try:
            return self.model_store.remove_snapshot(ref.specifier)
        except Exception:
            return False

    def mount_arg(self, ref: OciRef, dest: str | None = None) -> str | None:
        if not self.model_store:
            return None
        snapshot_dir = self.model_store.get_snapshot_directory_from_tag(ref.specifier)
        container_path = get_container_mount_path(snapshot_dir)

        # TODO: SElinux
        relabel = getattr(self, "relabel", "")
        return f"--mount=type=bind,src={container_path},destination={dest or MNT_DIR},ro{relabel}"

    def filenames(self, ref: OciRef) -> list[str]:
        if not self.model_store:
            raise ValueError("HTTP artifact strategy requires a model store")
        ref_file = self.model_store.get_ref_file(ref.specifier)
        if ref_file is None or not ref_file.model_files:
            raise ValueError(f"No model files found for artifact {str(ref)}")
        return sorted(file.name for file in ref_file.model_files)

    def inspect(self, ref: OciRef) -> str:
        client = OCIRegistryClient(ref.registry, ref.repository, ref.specifier)
        manifest, _ = client.get_manifest()
        return json.dumps(manifest)


class PodmanArtifactStrategy(BaseArtifactStrategy):
    def __init__(self, engine: str = "podman", *, model_store: ModelStore):
        super().__init__(engine=engine, model_store=model_store)

    def pull(self, ref: OciRef, cmd_args: list[str] | None = None) -> None:
        if cmd_args is None:
            cmd_args = []
        run_cmd([self.engine, "artifact", "pull", *cmd_args, str(ref)])

    def exists(self, ref: OciRef) -> bool:
        try:
            run_cmd([self.engine, "artifact", "inspect", str(ref)], ignore_stderr=True)
            return True
        except Exception:
            return False

    def mount_arg(self, ref: OciRef, dest: str | None = None) -> str:
        return f"--mount=type=artifact,src={str(ref)},destination={dest or MNT_DIR}"

    def remove(self, ref: OciRef, cmd_args: list[str] | None = None) -> bool:
        if cmd_args is None:
            cmd_args = []

        try:
            run_cmd([self.engine, "artifact", "rm", *cmd_args, str(ref)], ignore_stderr=True)
            return True
        except Exception:
            return False

    def filenames(self, ref: OciRef) -> list[str]:
        result = run_cmd(
            [self.engine, "artifact", "inspect", "--format", "{{json .Manifest}}", str(ref)],
            ignore_stderr=True,
        )

        payload = result.stdout.decode("utf-8").strip()
        manifest = json.loads(payload) if payload else {}
        names = []
        for layer in manifest.get("layers") or manifest.get("blobs") or []:
            annotations = layer.get("annotations") or {}
            filepath = annotations.get(oci_spec.LAYER_ANNOTATION_FILEPATH)
            metadata_value = annotations.get(oci_spec.LAYER_ANNOTATION_FILE_METADATA)
            if metadata_value is not None and filepath is None:
                metadata = oci_spec.FileMetadata.from_json(metadata_value)
                filepath = metadata.name
            if filepath is None:
                digest = layer.get("digest", "unknown")
                raise ValueError(f"Layer {digest} missing {oci_spec.LAYER_ANNOTATION_FILEPATH}")
            names.append(oci_spec.normalize_layer_filepath(filepath))

        if not names:
            raise ValueError(f"No layer filename annotations found for {str(ref)}")

        return sorted(names)

    def entrypoint_path(self, ref: OciRef, mount_dir: str | None = None) -> str:
        mount_dir = mount_dir or MNT_DIR
        filenames = self.filenames(ref)
        if not filenames:
            raise ValueError(f"No model files found for {str(ref)}")
        if len(filenames) == 1:
            if posixpath.dirname(filenames[0]):
                return posixpath.join(mount_dir, filenames[0])
            return mount_dir
        return posixpath.join(mount_dir, filenames[0])

    def inspect(self, ref: OciRef) -> str:
        result = run_cmd([self.engine, "artifact", "inspect", str(ref)], ignore_stderr=True)
        return result.stdout.decode("utf-8").strip()


class PodmanImageStrategy(BaseImageStrategy):
    def __init__(self, engine: str = "podman", *, model_store: ModelStore):
        super().__init__(engine=engine, model_store=model_store)

    def mount_arg(self, ref: OciRef, dest: str | None = None) -> str:
        return f"--mount=type=image,src={str(ref)},destination={dest or MNT_DIR},subpath=/models,rw=false"


class DockerImageStrategy(BaseImageStrategy):
    def __init__(self, engine: str = "docker", *, model_store: ModelStore):
        super().__init__(engine=engine, model_store=model_store)

    def mount_arg(self, ref: OciRef, dest: str | None = None) -> str | None:
        return f"--mount=type=volume,src={str(ref)},dst={dest or MNT_DIR},readonly"
