import json
import os
import stat
import tarfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# CNAI_ARTIFACT_TYPE is the media type for a model artifact manifest.
CNAI_ARTIFACT_TYPE = "application/vnd.cncf.model.manifest.v1+json"

# CNAI_CONFIG_MEDIA_TYPE is the media type for a model config object.
CNAI_CONFIG_MEDIA_TYPE = "application/vnd.cncf.model.config.v1+json"

# OCI_MANIFEST_MEDIA_TYPE is the standard OCI image manifest media type.
OCI_MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"

# LAYER_ANNOTATION_FILEPATH specifies the file path of the layer (string).
LAYER_ANNOTATION_FILEPATH = "org.cncf.model.filepath"

# LAYER_ANNOTATION_FILE_METADATA specifies file metadata JSON for the layer (string).
LAYER_ANNOTATION_FILE_METADATA = "org.cncf.model.file.metadata+json"

# LAYER_ANNOTATION_FILE_MEDIATYPE_UNTESTED indicates media type classification is untested (string).
LAYER_ANNOTATION_FILE_MEDIATYPE_UNTESTED = "org.cncf.model.file.mediatype.untested"

# ALLOWED_LAYER_MEDIA_TYPES contains CNAI layer media types from the model format spec.
ALLOWED_LAYER_MEDIA_TYPES = {
    "application/vnd.cncf.model.weight.v1.raw",
    "application/vnd.cncf.model.weight.v1.tar",
    "application/vnd.cncf.model.weight.v1.tar+gzip",
    "application/vnd.cncf.model.weight.v1.tar+zstd",
    "application/vnd.cncf.model.weight.config.v1.raw",
    "application/vnd.cncf.model.weight.config.v1.tar",
    "application/vnd.cncf.model.weight.config.v1.tar+gzip",
    "application/vnd.cncf.model.weight.config.v1.tar+zstd",
    "application/vnd.cncf.model.doc.v1.raw",
    "application/vnd.cncf.model.doc.v1.tar",
    "application/vnd.cncf.model.doc.v1.tar+gzip",
    "application/vnd.cncf.model.doc.v1.tar+zstd",
    "application/vnd.cncf.model.code.v1.raw",
    "application/vnd.cncf.model.code.v1.tar",
    "application/vnd.cncf.model.code.v1.tar+gzip",
    "application/vnd.cncf.model.code.v1.tar+zstd",
    "application/vnd.cncf.model.dataset.v1.raw",
    "application/vnd.cncf.model.dataset.v1.tar",
    "application/vnd.cncf.model.dataset.v1.tar+gzip",
    "application/vnd.cncf.model.dataset.v1.tar+zstd",
}

_MEDIATYPE_UNTESTED_VALUES = {"true", "false"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _require_str(value: Any, message: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(message)
    return value


def _require_int(value: Any, message: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(message)
    return value


def _typeflag_for_mode(mode: int) -> int:
    if stat.S_ISDIR(mode):
        return ord(tarfile.DIRTYPE)
    if stat.S_ISLNK(mode):
        return ord(tarfile.SYMTYPE)
    return ord(tarfile.REGTYPE)


def normalize_layer_filepath(value: str) -> str:
    value = _require_str(value, "layer annotation filepath must be a non-empty string")
    if os.path.isabs(value):
        raise ValueError("layer annotation filepath must be relative")
    normalized = os.path.normpath(value).lstrip(os.sep)
    if normalized in {"", "."} or normalized.startswith(".."):
        raise ValueError("layer annotation filepath must not escape the layer")
    return normalized


@dataclass(frozen=True)
class FileMetadata:
    name: str
    mode: int
    uid: int
    gid: int
    size: int
    mtime: str
    typeflag: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileMetadata":
        if not isinstance(data, dict):
            raise ValueError("file metadata must be a JSON object")
        name = _require_str(data.get("name"), "file metadata name is required")
        mode = _require_int(data.get("mode"), "file metadata mode is required")
        uid = _require_int(data.get("uid"), "file metadata uid is required")
        gid = _require_int(data.get("gid"), "file metadata gid is required")
        size = _require_int(data.get("size"), "file metadata size is required")
        mtime = _require_str(data.get("mtime"), "file metadata mtime is required")
        typeflag = _require_int(data.get("typeflag"), "file metadata typeflag is required")
        return cls(
            name=name,
            mode=mode,
            uid=uid,
            gid=gid,
            size=size,
            mtime=mtime,
            typeflag=typeflag,
        )

    @classmethod
    def from_json(cls, value: str) -> "FileMetadata":
        try:
            data = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("file metadata annotation must be valid JSON") from exc
        return cls.from_dict(data)

    @classmethod
    def from_path(cls, path: str, *, name: str | None = None) -> "FileMetadata":
        stat_result = os.stat(path, follow_symlinks=False)
        mtime = datetime.fromtimestamp(stat_result.st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        return cls(
            name=name or os.path.basename(path),
            mode=stat.S_IMODE(stat_result.st_mode),
            uid=stat_result.st_uid,
            gid=stat_result.st_gid,
            size=stat_result.st_size,
            mtime=mtime,
            typeflag=_typeflag_for_mode(stat_result.st_mode),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mode": self.mode,
            "uid": self.uid,
            "gid": self.gid,
            "size": self.size,
            "mtime": self.mtime,
            "typeflag": self.typeflag,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))


def is_cncf_artifact_manifest(manifest: dict[str, Any]) -> bool:
    artifact_type = manifest.get("artifactType")
    config_media = (manifest.get("config") or {}).get("mediaType", "")
    if artifact_type == CNAI_ARTIFACT_TYPE or config_media == CNAI_CONFIG_MEDIA_TYPE:
        return True
    layers = manifest.get("layers") or manifest.get("blobs") or []
    return any(layer.get("mediaType") in ALLOWED_LAYER_MEDIA_TYPES for layer in layers)


@dataclass
class Descriptor:
    media_type: str
    digest: str
    size: int
    annotations: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, allowed_media_types: set[str] | None = None) -> "Descriptor":
        media_type = _require_str(data.get("mediaType"), "descriptor mediaType is required")
        digest = _require_str(data.get("digest"), "descriptor digest is required")
        size = data.get("size")

        if size is None:
            raise ValueError("descriptor size is required")

        if allowed_media_types is not None:
            _require(
                media_type in allowed_media_types,
                f"descriptor mediaType '{media_type}' not in allowed set",
            )

        annotations = data.get("annotations") or {}
        if not isinstance(annotations, dict):
            raise ValueError("descriptor annotations must be a map")
        for key, value in annotations.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("descriptor annotations must be a string map")
        return cls(media_type=media_type, digest=digest, size=int(size), annotations=annotations)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "mediaType": self.media_type,
            "digest": self.digest,
            "size": self.size,
        }
        if self.annotations:
            data["annotations"] = self.annotations
        return data

    def filepath(self) -> str | None:
        value = self.annotations.get(LAYER_ANNOTATION_FILEPATH)
        if value is None:
            return None
        return normalize_layer_filepath(value)

    def file_metadata(self) -> FileMetadata | None:
        value = self.annotations.get(LAYER_ANNOTATION_FILE_METADATA)
        if value is None:
            return None
        return FileMetadata.from_json(value)

    def media_type_untested(self) -> bool | None:
        value = self.annotations.get(LAYER_ANNOTATION_FILE_MEDIATYPE_UNTESTED)
        if value is None:
            return None
        if value not in _MEDIATYPE_UNTESTED_VALUES:
            raise ValueError("layer annotation mediatype.untested must be 'true' or 'false'")
        return value == "true"


@dataclass
class Manifest:
    schema_version: int
    media_type: str
    artifact_type: str
    config: Descriptor
    layers: list[Descriptor]
    annotations: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Manifest":
        schema_version = data.get("schemaVersion", 2)
        media_type = data.get("mediaType") or OCI_MANIFEST_MEDIA_TYPE
        artifact_type = _require_str(data.get("artifactType"), "artifactType is required")
        _require(artifact_type == CNAI_ARTIFACT_TYPE, f"artifactType must be '{CNAI_ARTIFACT_TYPE}'")
        _require(media_type == OCI_MANIFEST_MEDIA_TYPE, f"mediaType must be '{OCI_MANIFEST_MEDIA_TYPE}'")

        config_dict = data.get("config") or {}
        config = Descriptor.from_dict(config_dict)
        _require(
            config.media_type == CNAI_CONFIG_MEDIA_TYPE,
            f"config mediaType must be '{CNAI_CONFIG_MEDIA_TYPE}'",
        )

        layers_data = data.get("layers") or []
        _require(
            isinstance(layers_data, list) and len(layers_data) > 0,
            "layers must be a non-empty list",
        )
        layers = [Descriptor.from_dict(layer, allowed_media_types=ALLOWED_LAYER_MEDIA_TYPES) for layer in layers_data]

        annotations = data.get("annotations") or {}
        return cls(
            schema_version=schema_version,
            media_type=media_type,
            artifact_type=artifact_type,
            config=config,
            layers=layers,
            annotations=annotations,
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schemaVersion": self.schema_version,
            "mediaType": self.media_type,
            "artifactType": self.artifact_type,
            "config": self.config.to_dict(),
            "layers": [layer.to_dict() for layer in self.layers],
        }
        if self.annotations:
            data["annotations"] = self.annotations
        return data
