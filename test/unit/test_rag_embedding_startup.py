"""A RAG embedding server that never goes ready must not be left behind.

``_start_rag_embedding_server`` starts the container and only then polls it for
readiness. The caller learns the container's name from the return value, so
raising past that point used to strand it: ``_serve_rag_pipeline`` had nothing
to hand ``_cleanup_servers``, and the network teardown behind it only disposes
of attached containers on podman.
"""

from argparse import Namespace
from unittest.mock import MagicMock

import pytest

import ramalama.plugins.runtimes.inference.llama_cpp as llama_cpp
import ramalama.plugins.runtimes.inference.rag.handler as handler
from ramalama.plugins.runtimes.inference.llama_cpp import LlamaCppPlugin


@pytest.fixture
def started_embedder(monkeypatch):
    """Drive _start_rag_embedding_server up to the readiness check.

    Returns the list that records ``_cleanup_servers`` calls.
    """
    cleaned: list = []

    embed_serve_args = Namespace(name="embed-server", port="8082", pull="missing")
    transport = MagicMock()
    transport.model_alias = "embed-model"
    transport.serve_nonblocking.return_value = "embed-proc"

    monkeypatch.setattr(llama_cpp, "set_accel_env_vars", lambda: None)
    monkeypatch.setattr(llama_cpp, "compute_serving_port", lambda *a, **k: "8082")
    monkeypatch.setattr(llama_cpp, "New", lambda *a, **k: transport)
    monkeypatch.setattr(llama_cpp, "assemble_command", lambda a: [])
    monkeypatch.setattr(handler, "_build_serve_args", lambda *a, **k: embed_serve_args)
    monkeypatch.setattr(handler, "_cleanup_servers", lambda *a: cleaned.append(a))
    return cleaned


def _start(monkeypatch, dryrun=False):
    args = Namespace(port="8080", model_args=Namespace(port="8081"), dryrun=dryrun, engine="podman")
    return LlamaCppPlugin()._start_rag_embedding_server(args), args


@pytest.mark.parametrize(
    "error",
    [
        # what _wait_for_server raises on its own timeout
        TimeoutError("did not become ready"),
        # service_ready_check is plugin code and may fail some other way; the
        # container is running either way, so the cleanup must not be
        # conditional on the exception type
        RuntimeError("ready check blew up"),
        KeyboardInterrupt(),
    ],
)
def test_failed_readiness_removes_the_embedder(error, started_embedder, monkeypatch):
    def boom(*a, **k):
        raise error

    monkeypatch.setattr(handler, "_wait_for_server", boom)

    with pytest.raises(type(error)):
        _start(monkeypatch)

    assert len(started_embedder) == 1, "a container that never went ready still holds its port"
    cleanup_args, serve_args, procs = started_embedder[0]
    assert [sa.name for sa in serve_args] == ["embed-server"]
    assert procs == ["embed-proc"]


def test_ready_embedder_is_kept(started_embedder, monkeypatch):
    monkeypatch.setattr(handler, "_wait_for_server", lambda *a, **k: None)

    (embed_serve_args, embed_proc), args = _start(monkeypatch)

    assert started_embedder == []
    assert embed_proc == "embed-proc"
    # the pipeline reaches it by container name over the private network
    assert args.embed_url == "http://embed-server:8082"
    assert embed_serve_args.name == "embed-server"


def test_dryrun_never_waits_or_cleans_up(started_embedder, monkeypatch):
    def unexpected(*a, **k):
        raise AssertionError("nothing was started, so there is nothing to wait for")

    monkeypatch.setattr(handler, "_wait_for_server", unexpected)

    _start(monkeypatch, dryrun=True)

    assert started_embedder == []
