from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ramalama.plugins.runtimes.inference.llama_cpp import LlamaCppPlugin
from ramalama.plugins.runtimes.inference.rag.handler import rag_handler
from ramalama.rag import RagSource, RagTransport


def _build_rag_transport(path: str, store: str, engine: str = "podman") -> RagTransport:
    args = Namespace(rag=path, store=store, engine=engine)
    return RagTransport(imodel=MagicMock(), cmd=[], args=args)


class TestRagTransportLocalDB:
    """Regression tests for issue #2526: locally generated RAG directories
    must resolve correctly even when their path has no ``:`` character
    (which would normally trigger OCI's ``:latest`` tag rewrite)."""

    def test_local_directory_classified_as_db(self, tmp_path: Path, force_oci_image: None) -> None:
        db_dir = tmp_path / "collection"
        db_dir.mkdir()

        rt = _build_rag_transport(str(db_dir), str(tmp_path / "store"))

        assert rt.kind is RagSource.DB

    def test_local_directory_exists_returns_true(self, tmp_path: Path, force_oci_image: None) -> None:
        db_dir = tmp_path / "collection"
        db_dir.mkdir()

        rt = _build_rag_transport(str(db_dir), str(tmp_path / "store"))

        # Before the fix, this asserted False because self.model had been
        # rewritten by OCI.__init__ to ``<db_dir>:latest``.
        assert rt.exists() is True

    def test_missing_local_path_classified_as_image(self, tmp_path: Path, force_oci_image: None) -> None:
        missing = tmp_path / "does-not-exist"

        rt = _build_rag_transport(str(missing), str(tmp_path / "store"))

        assert rt.kind is RagSource.IMAGE
        assert rt.model.endswith(":latest")


class TestRagTransportLocalhostPrefix:
    """Regression tests for local OCI image names without a registry prefix.

    A bare name like ``myrag`` must be prefixed with ``localhost/`` so that
    OCI resolution does not default to ``docker.io``.  The prefix is added
    by ``RagTransport.format_model`` and must be transparent to callers
    regardless of the container engine in use."""

    def test_bare_name_gets_localhost_prefix(self, tmp_path: Path, force_oci_image: None) -> None:
        rt = _build_rag_transport("myrag", str(tmp_path / "store"))

        assert rt.kind is RagSource.IMAGE
        assert rt.model == "localhost/myrag:latest"

    def test_slash_name_keeps_registry(self, tmp_path: Path, force_oci_image: None) -> None:
        rt = _build_rag_transport("quay.io/org/myrag", str(tmp_path / "store"))

        assert rt.kind is RagSource.IMAGE
        assert rt.model == "quay.io/org/myrag:latest"
        assert not rt.model.startswith("localhost/")

    def test_local_db_skips_prefix(self, tmp_path: Path, force_oci_image: None) -> None:
        db_dir = tmp_path / "mydb"
        db_dir.mkdir()

        rt = _build_rag_transport(str(db_dir), str(tmp_path / "store"))

        assert rt.kind is RagSource.DB
        assert rt.model == str(db_dir)
        assert "localhost" not in rt.model

    @pytest.mark.parametrize("engine", ["podman", "docker"])
    def test_bare_name_with_engine(self, tmp_path: Path, force_oci_image: None, engine: str) -> None:
        rt = _build_rag_transport("myrag", str(tmp_path / "store"), engine=engine)

        assert rt.kind is RagSource.IMAGE
        assert rt.model == "localhost/myrag:latest"

    def test_bare_name_syncs_args_rag(self, tmp_path: Path, force_oci_image: None) -> None:
        args = Namespace(rag="myrag", store=str(tmp_path / "store"), engine="podman")
        RagTransport(imodel=MagicMock(), cmd=[], args=args)

        assert args.rag == "localhost/myrag:latest"


class TestRagEmbeddingServeArgs:
    """Regression tests for issue #2836: ensure embedding server uses
    appropriate context and batch sizes (--batch-size, --ubatch-size)
    so chunks up to 2048 tokens (or user-specified embed_ctx_size) are accepted."""

    @patch("ramalama.plugins.loader.get_runtime", return_value=LlamaCppPlugin())
    @patch("ramalama.rag.Rag")
    @patch("ramalama.plugins.runtimes.inference.rag.handler.New")
    @patch("ramalama.plugins.runtimes.inference.rag.handler.compute_serving_port", side_effect=[8080, 8081])
    @patch("ramalama.plugins.runtimes.inference.rag.handler.set_accel_env_vars")
    def test_default_embed_batch_size_2048(
        self,
        mock_accel: MagicMock,
        mock_port: MagicMock,
        mock_new: MagicMock,
        mock_rag: MagicMock,
        mock_runtime: MagicMock,
    ) -> None:
        mock_transport = MagicMock()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_transport.serve_nonblocking.return_value = mock_proc
        mock_new.return_value = mock_transport

        args = Namespace(
            container=True,
            engine="podman",
            store="/tmp/store",
            dryrun=True,
            debug=False,
            image="rag-image",
            rag_image="rag-image",
            DOCUMENTS=["doc.pdf"],
            DESTINATION="myrag",
            embed_ctx_size=0,
            runtime="llama.cpp",
            subcommand="serve",
        )
        plugin = MagicMock()
        rag_handler(plugin, args)

        assert mock_new.call_count >= 2
        embed_call = mock_new.call_args_list[1]
        _, embed_serve_args = embed_call[0]

        assert embed_serve_args.ctx_size == 2048
        assert "--embedding" in embed_serve_args.runtime_args
        assert "--batch-size" in embed_serve_args.runtime_args
        assert "--ubatch-size" in embed_serve_args.runtime_args

        idx_batch = embed_serve_args.runtime_args.index("--batch-size")
        assert embed_serve_args.runtime_args[idx_batch + 1] == "2048"

        idx_ubatch = embed_serve_args.runtime_args.index("--ubatch-size")
        assert embed_serve_args.runtime_args[idx_ubatch + 1] == "2048"

        embed_call_serve = mock_transport.serve_nonblocking.call_args_list[1]
        _, called_cmd = embed_call_serve[0]
        assert "--ctx-size" in called_cmd
        assert called_cmd[called_cmd.index("--ctx-size") + 1] == "2048"
        assert "--batch-size" in called_cmd
        assert called_cmd[called_cmd.index("--batch-size") + 1] == "2048"
        assert "--ubatch-size" in called_cmd
        assert called_cmd[called_cmd.index("--ubatch-size") + 1] == "2048"

    @patch("ramalama.plugins.loader.get_runtime", return_value=LlamaCppPlugin())
    @patch("ramalama.rag.Rag")
    @patch("ramalama.plugins.runtimes.inference.rag.handler.New")
    @patch("ramalama.plugins.runtimes.inference.rag.handler.compute_serving_port", side_effect=[8080, 8081])
    @patch("ramalama.plugins.runtimes.inference.rag.handler.set_accel_env_vars")
    def test_custom_embed_ctx_size_propagates(
        self,
        mock_accel: MagicMock,
        mock_port: MagicMock,
        mock_new: MagicMock,
        mock_rag: MagicMock,
        mock_runtime: MagicMock,
    ) -> None:
        mock_transport = MagicMock()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_transport.serve_nonblocking.return_value = mock_proc
        mock_new.return_value = mock_transport

        args = Namespace(
            container=True,
            engine="podman",
            store="/tmp/store",
            dryrun=True,
            debug=False,
            image="rag-image",
            rag_image="rag-image",
            DOCUMENTS=["doc.pdf"],
            DESTINATION="myrag",
            embed_ctx_size=4096,
            runtime="llama.cpp",
            subcommand="serve",
        )
        plugin = MagicMock()
        rag_handler(plugin, args)

        assert mock_new.call_count >= 2
        embed_call = mock_new.call_args_list[1]
        _, embed_serve_args = embed_call[0]

        assert embed_serve_args.ctx_size == 4096
        idx_batch = embed_serve_args.runtime_args.index("--batch-size")
        assert embed_serve_args.runtime_args[idx_batch + 1] == "4096"
        idx_ubatch = embed_serve_args.runtime_args.index("--ubatch-size")
        assert embed_serve_args.runtime_args[idx_ubatch + 1] == "4096"

        embed_call_serve = mock_transport.serve_nonblocking.call_args_list[1]
        _, called_cmd = embed_call_serve[0]
        assert "--ctx-size" in called_cmd
        assert called_cmd[called_cmd.index("--ctx-size") + 1] == "4096"
        assert "--batch-size" in called_cmd
        assert called_cmd[called_cmd.index("--batch-size") + 1] == "4096"
        assert "--ubatch-size" in called_cmd
        assert called_cmd[called_cmd.index("--ubatch-size") + 1] == "4096"
