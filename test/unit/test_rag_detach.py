"""``serve --rag -d`` must leave its containers running.

Detaching backgrounds the RAG proxy, but a proxy on its own answers nothing: it
forwards to the model server and the embedding server, and reaches both over a
private network. Three independent cleanup layers used to assume the dispatch
call blocks for the lifetime of the proxy, so under --detach all three fired the
instant the proxy was backgrounded and destroyed the whole pipeline.
"""

from argparse import Namespace
from unittest.mock import MagicMock

import pytest

import ramalama.plugins.runtimes.inference.rag.handler as handler
from ramalama.plugins.runtimes.inference.llama_cpp import LlamaCppPlugin
from ramalama.rag import RagTransport


@pytest.fixture
def cleanup_spy(monkeypatch):
    """Record the cleanup the pipeline performs instead of performing it."""
    calls: dict[str, list] = {"cleanup": [], "report": [], "remove_network": []}

    monkeypatch.setattr(handler, "_setup_rag_network", lambda args: True)
    monkeypatch.setattr(handler, "_cleanup_servers", lambda *a: calls["cleanup"].append(a))
    monkeypatch.setattr(handler, "_report_skipped_cleanup", lambda *a: calls["report"].append(a))
    monkeypatch.setattr("ramalama.engine.remove_network", lambda *a: calls["remove_network"].append(a))
    return calls


def _proxy_args(detach):
    return Namespace(
        detach=detach,
        name=None,
        network="ramalama-net-test",
        engine="podman",
        dryrun=False,
        model_args=Namespace(name="model-server"),
    )


def _run_pipeline(args, monkeypatch, dispatch=None):
    plugin = LlamaCppPlugin()
    monkeypatch.setattr(plugin, "_start_rag_embedding_server", lambda a: (Namespace(name="embed-server"), None))
    plugin._serve_rag_pipeline(args, dispatch or (lambda: None))


class TestDetachedPipelineSurvives:
    def test_helpers_and_network_are_left_running(self, cleanup_spy, monkeypatch):
        _run_pipeline(_proxy_args(detach=True), monkeypatch)

        assert cleanup_spy["cleanup"] == [], "the embedding server must outlive a detached proxy"
        assert cleanup_spy["remove_network"] == [], "removing the network takes the containers with it"
        assert len(cleanup_spy["report"]) == 1

    def test_report_names_all_three_containers(self, cleanup_spy, monkeypatch):
        args = _proxy_args(detach=True)
        _run_pipeline(args, monkeypatch)

        reported_args, serve_args, network_created, reason = cleanup_spy["report"][0]
        assert reason == "--detach"
        assert network_created is True
        names = [getattr(sa, "name", None) for sa in serve_args]
        # the proxy itself, the model server it forwards to, and the embedder
        assert names == [args.name, "model-server", "embed-server"]

    def test_proxy_is_named_so_it_can_be_reported(self, cleanup_spy, monkeypatch):
        """The engine would otherwise generate a name it keeps to itself."""
        args = _proxy_args(detach=True)
        _run_pipeline(args, monkeypatch)

        assert args.name, "a detached proxy the user cannot name is a proxy they cannot stop"

    def test_explicit_name_is_preserved(self, cleanup_spy, monkeypatch):
        args = _proxy_args(detach=True)
        args.name = "chosen-by-the-user"
        _run_pipeline(args, monkeypatch)

        assert args.name == "chosen-by-the-user"


class TestForegroundPipelineStillCleansUp:
    def test_helpers_and_network_are_torn_down(self, cleanup_spy, monkeypatch):
        _run_pipeline(_proxy_args(detach=False), monkeypatch)

        assert len(cleanup_spy["cleanup"]) == 1
        assert len(cleanup_spy["remove_network"]) == 1
        assert cleanup_spy["report"] == []

    def test_a_failed_dispatch_cleans_up_even_when_detaching(self, cleanup_spy, monkeypatch):
        """Nothing survived the failure, so there is nothing to keep alive."""

        def boom():
            raise RuntimeError("podman run failed")

        with pytest.raises(RuntimeError):
            _run_pipeline(_proxy_args(detach=True), monkeypatch, dispatch=boom)

        assert len(cleanup_spy["cleanup"]) == 1
        assert len(cleanup_spy["remove_network"]) == 1
        assert cleanup_spy["report"] == []


class TestRagTransportModelServer:
    """RagTransport.serve owns the model server the proxy forwards to."""

    def _serve(self, monkeypatch, detach, fail=False):
        stopped = []
        monkeypatch.setattr("ramalama.rag.stop_container", lambda a, name, remove=False: stopped.append(name))

        args = Namespace(
            rag="localhost/rag:test",
            store="/tmp/store",
            engine="podman",
            dryrun=True,
            detach=detach,
            model_args=Namespace(name="model-server"),
        )
        imodel = MagicMock()
        # serve() names the model server through the backing transport
        imodel.get_container_name.return_value = "model-server"
        imodel.serve_nonblocking.return_value = None
        transport = RagTransport(imodel=imodel, cmd=[], args=args)

        def execute(cmd, a):
            if fail:
                raise RuntimeError("podman run failed")

        monkeypatch.setattr(transport, "execute_command", execute)
        if fail:
            with pytest.raises(RuntimeError):
                transport.serve(args, [])
        else:
            transport.serve(args, [])
        return stopped

    def test_detached_keeps_the_model_server(self, monkeypatch, force_oci_image):
        assert self._serve(monkeypatch, detach=True) == []

    def test_foreground_stops_the_model_server(self, monkeypatch, force_oci_image):
        assert self._serve(monkeypatch, detach=False) == ["model-server"]

    def test_failed_start_stops_the_model_server(self, monkeypatch, force_oci_image):
        assert self._serve(monkeypatch, detach=True, fail=True) == ["model-server"]
