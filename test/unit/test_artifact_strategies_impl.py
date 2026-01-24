from ramalama.artifacts import strategies


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
    strat = strategies.PodmanArtifactStrategy(engine="podman")
    strat.pull("artifact:latest")
    assert rec.calls[0][0] == ["podman", "artifact", "pull", "artifact:latest"]
    assert strat.mount_arg("artifact:latest").startswith("--mount=type=artifact")


def test_podman_artifact_exists(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(strategies, "run_cmd", rec)
    strat = strategies.PodmanArtifactStrategy(engine="podman")
    assert strat.exists("artifact:latest") is True
    assert rec.calls[0][0] == ["podman", "artifact", "inspect", "artifact:latest"]


def test_podman_image_path(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(strategies, "run_cmd", rec)
    strat = strategies.PodmanImageStrategy(engine="podman")
    strat.pull("image:latest")
    assert rec.calls[0][0] == ["podman", "pull", "image:latest"]
    assert strat.mount_arg("image:latest").startswith("--mount=type=image")


def test_docker_image_path(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(strategies, "run_cmd", rec)
    strat = strategies.DockerImageStrategy(engine="docker")
    strat.pull("image:latest")
    assert rec.calls[0][0] == ["docker", "pull", "image:latest"]
    assert strat.exists("image:latest") is True
    assert rec.calls[1][0] == ["docker", "image", "inspect", "image:latest"]
    assert strat.mount_arg("image:latest") is None


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

    def downloader(**kwargs):
        called.append(kwargs)
        return True

    monkeypatch.setattr(strategies, "download_oci_artifact", downloader)
    store = StoreStub()
    strat = strategies.HttpBindStrategy(model_store=store)
    strat.pull("oci://example.com/ns/model:tag")
    assert called[0]["registry"] == "example.com"
    assert called[0]["reference"] == "ns/model:tag"
    assert called[0]["model_tag"] == "tag"
    assert strat.exists("oci://example.com/ns/model:tag") is True
    assert store.last_tag == "tag"
    assert strat.mount_arg() is None
