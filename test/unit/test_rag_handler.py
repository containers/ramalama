from argparse import Namespace

import pytest

import ramalama.plugins.runtimes.inference.rag.handler as handler


def _capture_report(args, all_serve_args, network_created, monkeypatch):
    lines: list[str] = []
    monkeypatch.setattr(handler, "perror", lambda *a, **k: lines.append(" ".join(str(x) for x in a)))
    handler._report_skipped_cleanup(args, all_serve_args, network_created)
    return lines


@pytest.mark.parametrize(
    "engine,expected_net_rm",
    [
        # podman network rm supports -f to disconnect lingering containers
        ("podman", "podman network rm -f ramalama-net-abc"),
        # docker network rm has no -f flag; the suggested command must omit it
        ("docker", "docker network rm ramalama-net-abc"),
    ],
)
def test_report_skipped_cleanup_network_rm_flag(engine, expected_net_rm, monkeypatch):
    args = Namespace(engine=engine, network="ramalama-net-abc")
    serve_args = [Namespace(name="rag-embed"), Namespace(name="rag-docling")]
    lines = _capture_report(args, serve_args, network_created=True, monkeypatch=monkeypatch)

    cleanup = next(line for line in lines if line.startswith("clean up with:"))
    assert f"{engine} rm -f rag-embed rag-docling" in cleanup
    assert expected_net_rm in cleanup
    # docker must never be told to force-remove a network
    if engine == "docker":
        assert "network rm -f" not in cleanup


def test_report_skipped_cleanup_omits_network_when_not_created(monkeypatch):
    args = Namespace(engine="docker", network="ramalama-net-abc")
    serve_args = [Namespace(name="rag-embed")]
    lines = _capture_report(args, serve_args, network_created=False, monkeypatch=monkeypatch)

    cleanup = next(line for line in lines if line.startswith("clean up with:"))
    assert "network rm" not in cleanup
    assert "docker rm -f rag-embed" in cleanup


def test_cleanup_servers_dryrun_does_not_touch_engine(monkeypatch):
    # On a dry run nothing was started, so cleanup must not shell out to the
    # engine to stop/remove containers that never existed.
    calls = []
    monkeypatch.setattr(
        "ramalama.engine.stop_container",
        lambda *a, **k: calls.append(a),
    )
    args = Namespace(engine="podman", dryrun=True)
    serve_args = [Namespace(name="rag-embed"), Namespace(name="rag-docling")]

    handler._cleanup_servers(args, serve_args, [None, None])

    assert calls == []


def test_cleanup_servers_stops_containers_when_not_dryrun(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "ramalama.engine.stop_container",
        lambda stop_args, name, remove=False: calls.append((name, remove)),
    )
    args = Namespace(engine="podman", dryrun=False)
    serve_args = [Namespace(name="rag-embed"), Namespace(name="rag-docling")]

    handler._cleanup_servers(args, serve_args, [None, None])

    assert calls == [("rag-embed", True), ("rag-docling", True)]
