from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ramalama.annotations import AnnotationTitle

CNAI_ARTIFACT_TYPE = "application/vnd.cnai.model.manifest.v1+json"
CNAI_CONFIG_MEDIA_TYPE = "application/vnd.cnai.model.config.v1+json"
OCI_MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"

# Allow the CNAI layer media types from the model format spec.
ALLOWED_LAYER_MEDIA_TYPES = {
    "application/vnd.cnai.model.weight.v1.raw",
    "application/vnd.cnai.model.weight.v1.tar",
    "application/vnd.cnai.model.weight.v1.tar+gzip",
    "application/vnd.cnai.model.weight.v1.tar+zstd",
    "application/vnd.cnai.model.weight.config.v1.raw",
    "application/vnd.cnai.model.weight.config.v1.tar",
    "application/vnd.cnai.model.weight.config.v1.tar+gzip",
    "application/vnd.cnai.model.weight.config.v1.tar+zstd",
    "application/vnd.cnai.model.doc.v1.raw",
    "application/vnd.cnai.model.doc.v1.tar",
    "application/vnd.cnai.model.doc.v1.tar+gzip",
    "application/vnd.cnai.model.doc.v1.tar+zstd",
    "application/vnd.cnai.model.code.v1.raw",
    "application/vnd.cnai.model.code.v1.tar",
    "application/vnd.cnai.model.code.v1.tar+gzip",
    "application/vnd.cnai.model.code.v1.tar+zstd",
    "application/vnd.cnai.model.dataset.v1.raw",
    "application/vnd.cnai.model.dataset.v1.tar",
    "application/vnd.cnai.model.dataset.v1.tar+gzip",
    "application/vnd.cnai.model.dataset.v1.tar+zstd",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


@dataclass
class Descriptor:
    media_type: str
    digest: str
    size: int
    annotations: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, allowed_media_types: Optional[set[str]] = None) -> "Descriptor":
        media_type = data.get("mediaType")
        digest = data.get("digest")
        size = data.get("size")

        _require(media_type, "descriptor mediaType is required")
        _require(digest, "descriptor digest is required")
        _require(size is not None, "descriptor size is required")

        if allowed_media_types is not None:
            _require(
                media_type in allowed_media_types,
                f"descriptor mediaType '{media_type}' not in allowed set",
            )

        annotations = data.get("annotations") or {}
        return cls(media_type=media_type, digest=digest, size=int(size), annotations=annotations)

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "mediaType": self.media_type,
            "digest": self.digest,
            "size": self.size,
        }
        if self.annotations:
            data["annotations"] = self.annotations
        return data

    def title(self) -> Optional[str]:
        return self.annotations.get(AnnotationTitle)


@dataclass
class Manifest:
    schema_version: int
    media_type: str
    artifact_type: str
    config: Descriptor
    layers: List[Descriptor]
    annotations: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Manifest":
        schema_version = data.get("schemaVersion", 2)
        media_type = data.get("mediaType") or OCI_MANIFEST_MEDIA_TYPE
        artifact_type = data.get("artifactType")
        _require(artifact_type == CNAI_ARTIFACT_TYPE, f"artifactType must be '{CNAI_ARTIFACT_TYPE}'")
        _require(media_type == OCI_MANIFEST_MEDIA_TYPE, f"mediaType must be '{OCI_MANIFEST_MEDIA_TYPE}'")

        config_dict = data.get("config") or {}
        config = Descriptor.from_dict(config_dict)
        _require(
            config.media_type == CNAI_CONFIG_MEDIA_TYPE,
            f"config mediaType must be '{CNAI_CONFIG_MEDIA_TYPE}'",
        )

        layers_data = data.get("layers") or []
        _require(isinstance(layers_data, list) and layers_data, "layers must be a non-empty list")
        layers = [
            Descriptor.from_dict(layer, allowed_media_types=ALLOWED_LAYER_MEDIA_TYPES) for layer in layers_data
        ]

        annotations = data.get("annotations") or {}
        return cls(
            schema_version=schema_version,
            media_type=media_type,
            artifact_type=artifact_type,
            config=config,
            layers=layers,
            annotations=annotations,
        )

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "schemaVersion": self.schema_version,
            "mediaType": self.media_type,
            "artifactType": self.artifact_type,
            "config": self.config.to_dict(),
            "layers": [layer.to_dict() for layer in self.layers],
        }
        if self.annotations:
            data["annotations"] = self.annotations
        return data
