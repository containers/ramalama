from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

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
