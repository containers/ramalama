import pytest

from ramalama.artifacts import strategy as strat


def make_runner(success: bool = True):
    def _runner(cmd, **kwargs):
        if not success:
            raise RuntimeError("fail")
        return None

    return _runner


def test_podman_artifact_supported(monkeypatch):
    monkeypatch.setattr(strat, "engine_version", lambda e: "5.7.1")
    monkeypatch.setattr(strat, "run_cmd", make_runner(success=True))
    strat.clear_probe_cache()

    caps = strat.probe_capabilities("podman")
    assert caps.artifact_supported is True
    assert caps.order[0] == strat.STRATEGY_PODMAN_ARTIFACT
    assert strat.select_strategy(strat.STRATEGY_AUTO, caps) == strat.STRATEGY_PODMAN_ARTIFACT


def test_podman_below_min_version(monkeypatch):
    monkeypatch.setattr(strat, "engine_version", lambda e: "5.6.9")
    monkeypatch.setattr(strat, "run_cmd", make_runner(success=True))
    strat.clear_probe_cache()

    caps = strat.probe_capabilities("podman")
    assert caps.artifact_supported is False
    assert caps.order[0] == strat.STRATEGY_PODMAN_IMAGE

    with pytest.raises(ValueError):
        strat.select_strategy(strat.STRATEGY_PODMAN_ARTIFACT, caps)
    assert strat.select_strategy(strat.STRATEGY_AUTO, caps) == strat.STRATEGY_PODMAN_IMAGE


def test_podman_artifact_command_failure(monkeypatch):
    monkeypatch.setattr(strat, "engine_version", lambda e: "5.7.2")
    monkeypatch.setattr(strat, "run_cmd", make_runner(success=False))
    strat.clear_probe_cache()

    caps = strat.probe_capabilities("podman")
    assert caps.artifact_supported is False
    assert caps.order[0] == strat.STRATEGY_PODMAN_IMAGE


def test_docker_path(monkeypatch):
    strat.clear_probe_cache()
    caps = strat.probe_capabilities("docker")
    assert caps.is_docker is True
    assert caps.order == [strat.STRATEGY_HTTP_BIND]

    with pytest.raises(ValueError):
        strat.select_strategy(strat.STRATEGY_PODMAN_IMAGE, caps)
    with pytest.raises(ValueError):
        strat.select_strategy(strat.STRATEGY_PODMAN_ARTIFACT, caps)
    assert strat.select_strategy(strat.STRATEGY_AUTO, caps) == strat.STRATEGY_HTTP_BIND


def test_http_bind_override_always_allowed(monkeypatch):
    strat.clear_probe_cache()
    caps = strat.probe_capabilities(None)
    assert strat.select_strategy(strat.STRATEGY_HTTP_BIND, caps) == strat.STRATEGY_HTTP_BIND
