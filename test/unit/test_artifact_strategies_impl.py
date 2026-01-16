from unittest.mock import Mock

from ramalama.oci_tools import OciRef
from ramalama.transports.oci import strategies


class Recorder:
    def __init__(self, should_fail=False):
        self.calls = []
        self.should_fail = should_fail

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if self.should_fail:
            raise RuntimeError("fail")
        return None


def test_podman_artifact_mount_and_pull(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(strategies, "run_cmd", rec)
    strat = strategies.PodmanArtifactStrategy(engine="podman", model_store=Mock())
    ref = OciRef.from_ref_string("artifact:latest")
    strat.pull(ref)
    assert rec.calls[0][0] == ["podman", "artifact", "pull", str(ref)]
    assert strat.mount_arg(ref).startswith("--mount=type=artifact")


def test_podman_artifact_exists(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(strategies, "run_cmd", rec)
    strat = strategies.PodmanArtifactStrategy(engine="podman", model_store=Mock())
    ref = OciRef.from_ref_string("artifact:latest")
    assert strat.exists(ref) is True
    assert rec.calls[0][0] == ["podman", "artifact", "inspect", str(ref)]


def test_podman_image_path(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(strategies, "run_cmd", rec)
    strat = strategies.PodmanImageStrategy(engine="podman", model_store=Mock())
    ref = OciRef.from_ref_string("image:latest")
    strat.pull(ref)
    assert rec.calls[0][0] == ["podman", "pull", str(ref)]
    assert strat.mount_arg(ref).startswith("--mount=type=image")


def test_docker_image_path(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(strategies, "run_cmd", rec)
    strat = strategies.DockerImageStrategy(engine="docker", model_store=Mock())
    ref = OciRef.from_ref_string("image:latest")
    strat.pull(ref)
    assert rec.calls[0][0] == ["docker", "pull", str(ref)]
    assert strat.exists(ref) is True
    assert rec.calls[1][0] == ["docker", "image", "inspect", str(ref)]
    assert strat.mount_arg(ref).startswith("--mount=type=volume")


def test_http_bind_path_fetch_and_exists(monkeypatch):
    called = []

    class StoreStub:
        def __init__(self, cached=True):
            self.cached = cached
            self.last_tag = None

        def get_cached_files(self, model_tag):
            self.last_tag = model_tag
            cached_files = ["blob"] if self.cached else []
            return None, cached_files, self.cached

        def get_snapshot_directory_from_tag(self, model_tag):
            return f"/snapshots/{model_tag}"

    def downloader(**kwargs):
        called.append(kwargs)
        return True

    monkeypatch.setattr(strategies, "download_oci_artifact", downloader)
    store = StoreStub()
    strat = strategies.HttpArtifactStrategy(engine="docker", model_store=store)
    ref = OciRef.from_ref_string("example.com/ns/model:tag")
    strat.pull(ref)
    assert called[0]["reference"] == str(ref)
    assert called[0]["model_tag"] == "tag"
    assert strat.exists(ref) is True
    assert store.last_tag == "tag"
    mount_arg = strat.mount_arg(ref)
    assert "type=bind" in mount_arg
    assert "destination=/mnt/models" in mount_arg
