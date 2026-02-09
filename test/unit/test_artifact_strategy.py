from ramalama.common import SemVer
from ramalama.transports.oci import strategies
from ramalama.transports.oci import strategy as strat


def test_podman_artifact_supported(monkeypatch):
    monkeypatch.setattr(strat, "engine_version", lambda e: SemVer(5, 7, 1))
    strategy_cls = strat.get_engine_artifact_strategy("podman", "podman")
    assert strategy_cls is strategies.PodmanArtifactStrategy


def test_podman_below_min_version(monkeypatch):
    monkeypatch.setattr(strat, "engine_version", lambda e: SemVer(5, 6, 9))
    strategy_cls = strat.get_engine_artifact_strategy("podman", "podman")
    assert strategy_cls is strategies.HttpArtifactStrategy


def test_docker_path():
    assert strat.get_engine_image_strategy("docker", "docker") is strategies.DockerImageStrategy
    assert strat.get_engine_artifact_strategy("docker", "docker") is strategies.HttpArtifactStrategy
