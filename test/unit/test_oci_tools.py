import json
import subprocess
from datetime import datetime, timedelta
from types import SimpleNamespace

from ramalama import oci_tools
from ramalama.annotations import AnnotationModel
from ramalama.arg_types import EngineArgs
from ramalama.common import SemVer


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


def test_list_models_timezones_in_utc(monkeypatch):
    label_output = (
        '{"name":"oci://localhost/demo:latest","modified":"2026-01-01 00:00:00 +0000","size":123,"ID":"sha256:a"},'
    )

    def fake_run_cmd(args, **kwargs):
        if args[:4] == ["podman", "images", "--filter", "label=org.containers.type"]:
            return _result(label_output)
        if args[:4] == ["podman", "images", "--filter", "manifest=true"]:
            return _result("")
        if args[:3] == ["podman", "artifact", "ls"]:
            return _result("")
        raise AssertionError(f"Unexpected command: {args}")

    monkeypatch.setattr(oci_tools, "run_cmd", fake_run_cmd)
    monkeypatch.setattr(oci_tools, "engine_supports_manifest_attributes", lambda engine: False)

    models = oci_tools.list_models(EngineArgs(engine="podman"))
    assert all(isinstance(m['modified'], datetime) for m in models)
    assert all(m['modified'].utcoffset() == timedelta(0) for m in models)


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


def test_list_artifacts_handles_unsupported_format_flag(monkeypatch):
    def fake_run_cmd(args, **kwargs):
        if args[:3] == ["podman", "artifact", "ls"]:
            raise subprocess.CalledProcessError(125, args)
        raise AssertionError(f"Unexpected command: {args}")

    monkeypatch.setattr(oci_tools, "run_cmd", fake_run_cmd)

    models = oci_tools.list_artifacts(EngineArgs(engine="podman"))

    assert models == []


def test_engine_supports_manifest_attributes_uses_semver(monkeypatch):
    monkeypatch.setattr(oci_tools, "engine_version", lambda engine: SemVer(10, 0, 0))
    assert oci_tools.engine_supports_manifest_attributes("podman") is True

    monkeypatch.setattr(oci_tools, "engine_version", lambda engine: SemVer(4, 9, 9))
    assert oci_tools.engine_supports_manifest_attributes("podman") is False


def test_list_manifests_parses_modified_when_engine_lacks_attribute_support(monkeypatch):
    """Regression test for https://github.com/containers/ramalama/issues/2586.

    When engine_supports_manifest_attributes() returns False, list_manifests()
    previously returned the raw JSON dicts, leaving ``modified`` as a plain
    string.  GlobalModelStore.list_models() then called .timestamp() on that
    string, triggering an AttributeError.

    The fix ensures parse_datetime() is applied before returning, so callers
    always receive a datetime (or None) — never a bare string.
    """
    manifests_output = (
        '{"name":"oci://localhost/mymodel:latest","modified":"2026-03-01 12:00:00 +0000",'
        '"size":500,"ID":"sha256:d"},'
    )

    def fake_run_cmd(args, **kwargs):
        if args[:4] == ["podman", "images", "--filter", "manifest=true"]:
            return _result(manifests_output)
        raise AssertionError(f"Unexpected command: {args}")

    monkeypatch.setattr(oci_tools, "run_cmd", fake_run_cmd)
    monkeypatch.setattr(oci_tools, "engine_supports_manifest_attributes", lambda engine: False)

    models = oci_tools.list_manifests(EngineArgs(engine="podman"))

    assert len(models) == 1
    model = models[0]
    assert model["name"] == "oci://localhost/mymodel:latest"
    assert model["size"] == 500
    # ``modified`` must be a datetime — not a raw string — so that
    # GlobalModelStore.list_models() can safely call .timestamp() on it.
    assert isinstance(model["modified"], datetime), (
        f"Expected datetime, got {type(model['modified'])}: {model['modified']!r}"
    )
