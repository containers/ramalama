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


def test_podman_artifact_mount_and_pull():
    rec = Recorder()
    strat = strategies.PodmanArtifactStrategy(engine="podman", reference="artifact:latest", runner=rec)
    strat.pull()
    assert rec.calls[0][0] == ["podman", "artifact", "pull", "artifact:latest"]
    assert strat.mount_arg().startswith("--mount=type=artifact")


def test_podman_artifact_exists():
    rec = Recorder()
    strat = strategies.PodmanArtifactStrategy(engine="podman", reference="artifact:latest", runner=rec)
    assert strat.exists() is True
    assert rec.calls[0][0] == ["podman", "artifact", "inspect", "artifact:latest"]


def test_podman_image_path():
    rec = Recorder()
    strat = strategies.PodmanImageStrategy(engine="podman", reference="image:latest", runner=rec)
    strat.pull()
    assert rec.calls[0][0] == ["podman", "pull", "image:latest"]
    assert strat.mount_arg().startswith("--mount=type=image")


def test_http_bind_path_fetch_and_exists():
    called = []

    def fetcher(ref, check_only=False):
        called.append((ref, check_only))
        if check_only:
            return True
        return None

    strat = strategies.HttpBindStrategy(reference="oci://example/model", fetcher=fetcher)
    strat.pull()
    assert called[0] == ("oci://example/model", False)
    assert strat.exists() is True
    assert called[1] == ("oci://example/model", True)
    assert strat.mount_arg() is None
