import json
from types import SimpleNamespace

from ramalama import oci_tools
from ramalama.annotations import AnnotationModel
from ramalama.arg_types import EngineArgs


def _result(text: str):
    return SimpleNamespace(stdout=text.encode("utf-8"))


def test_list_models_dedupes_labelled_and_manifest_entries(monkeypatch):
    label_output = (
        '{"name":"oci://localhost/demo:latest","modified":"2026-01-01 00:00:00 +0000","size":123,"ID":"sha256:a"},'
    )
    manifest_output = (
        '{"name":"oci://localhost/demo:latest","modified":"2026-01-01 00:00:00 +0000","size":123,"ID":"sha256:b"},'
    )

    def fake_run_cmd(args, **kwargs):
        if args[:4] == ["podman", "images", "--filter", "label=org.containers.type"]:
            return _result(label_output)
        if args[:4] == ["podman", "images", "--filter", "manifest=true"]:
            return _result(manifest_output)
        if args[:3] == ["podman", "artifact", "ls"]:
            return _result("")
        raise AssertionError(f"Unexpected command: {args}")

    monkeypatch.setattr(oci_tools, "run_cmd", fake_run_cmd)
    monkeypatch.setattr(oci_tools, "engine_supports_manifest_attributes", lambda engine: False)

    models = oci_tools.list_models(EngineArgs(engine="podman"))

    assert len(models) == 1
    assert models[0]["name"] == "oci://localhost/demo:latest"
    assert models[0]["size"] == 123
    assert models[0]["modified"].endswith("+00:00")


def test_list_manifests_filters_by_annotation(monkeypatch):
    manifests_output = """\
{"name":"oci://localhost/annotation-filtered:latest","modified":"2026-01-01 00:00:00 +0000","size":456,"ID":"sha256:c"},
"""
    inspect_payload = {
        "manifests": [
            {
                "digest": "sha256:child",
                "annotations": {AnnotationModel: "true"},
            }
        ]
    }

    def fake_run_cmd(args, **kwargs):
        if args[:4] == ["podman", "images", "--filter", "manifest=true"]:
            return _result(manifests_output)
        if args[:3] == ["podman", "manifest", "inspect"]:
            return _result(json.dumps(inspect_payload))
        raise AssertionError(f"Unexpected command: {args}")

    monkeypatch.setattr(oci_tools, "run_cmd", fake_run_cmd)
    monkeypatch.setattr(oci_tools, "engine_supports_manifest_attributes", lambda engine: True)

    models = oci_tools.list_manifests(EngineArgs(engine="podman"))

    assert len(models) == 1
    assert models[0]["name"] == "oci://localhost/annotation-filtered:latest"
    assert models[0]["size"] == 456
