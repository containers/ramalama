import json

import pytest

from ramalama.annotations import AnnotationTitle
from ramalama.artifacts import spec as oci_spec


def _valid_manifest():
    return {
        "schemaVersion": 2,
        "mediaType": oci_spec.OCI_MANIFEST_MEDIA_TYPE,
        "artifactType": oci_spec.CNAI_ARTIFACT_TYPE,
        "config": {
            "mediaType": oci_spec.CNAI_CONFIG_MEDIA_TYPE,
            "digest": "sha256:d5815835051dd97d800a03f641ed8162877920e734d3d705b698912602b8c763",
            "size": 301,
        },
        "layers": [
            {
                "mediaType": "application/vnd.cnai.model.weight.v1.tar",
                "digest": "sha256:3f907c1a03bf20f20355fe449e18ff3f9de2e49570ffb536f1a32f20c7179808",
                "size": 30327160,
                "annotations": {AnnotationTitle: "model.gguf"},
            }
        ],
        "annotations": {AnnotationTitle: "example-manifest"},
    }


def test_round_trip_manifest():
    manifest_dict = _valid_manifest()
    manifest = oci_spec.Manifest.from_dict(manifest_dict)
    assert manifest.artifact_type == oci_spec.CNAI_ARTIFACT_TYPE
    assert manifest.config.media_type == oci_spec.CNAI_CONFIG_MEDIA_TYPE
    assert manifest.layers[0].title() == "model.gguf"

    round_trip = manifest.to_dict()
    assert round_trip == manifest_dict
    assert json.loads(json.dumps(round_trip)) == json.loads(json.dumps(manifest_dict))


def test_reject_wrong_artifact_type():
    manifest_dict = _valid_manifest()
    manifest_dict["artifactType"] = "application/vnd.ramalama.model.gguf"
    with pytest.raises(ValueError):
        oci_spec.Manifest.from_dict(manifest_dict)


def test_reject_missing_config():
    manifest_dict = _valid_manifest()
    manifest_dict["config"] = {}
    with pytest.raises(ValueError):
        oci_spec.Manifest.from_dict(manifest_dict)


def test_reject_invalid_layer_media_type():
    manifest_dict = _valid_manifest()
    manifest_dict["layers"][0]["mediaType"] = "application/unknown"
    with pytest.raises(ValueError):
        oci_spec.Manifest.from_dict(manifest_dict)


def test_reject_wrong_config_media_type():
    manifest_dict = _valid_manifest()
    manifest_dict["config"]["mediaType"] = "application/vnd.oci.image.config.v1+json"
    with pytest.raises(ValueError):
        oci_spec.Manifest.from_dict(manifest_dict)
