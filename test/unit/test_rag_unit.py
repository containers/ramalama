from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ramalama.rag import (
    RAG_ROLE_CAPTIONING,
    RAG_ROLE_DOCLING,
    RAG_ROLE_EMBEDDING,
    RAG_ROLE_MODEL,
    RagSource,
    RagTransport,
    rag_stack_base_name,
    rag_stack_container_name,
)


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


class TestRagStackNames:
    def test_explicit_base_name_is_preserved(self) -> None:
        base, generated = rag_stack_base_name("ragtest")
        assert base == "ragtest"
        assert generated is False

    def test_generated_base_name_uses_ramalama_prefix(self) -> None:
        name, generated = rag_stack_base_name(None)
        assert generated is True
        assert name.startswith("ramalama-")
        assert len(name) > len("ramalama-")

    def test_role_suffixes(self) -> None:
        assert rag_stack_container_name("ragtest", RAG_ROLE_DOCLING) == "ragtest-docling"
        assert rag_stack_container_name("ragtest", RAG_ROLE_EMBEDDING) == "ragtest-embedding"
        assert rag_stack_container_name("ragtest", RAG_ROLE_CAPTIONING) == "ragtest-captioning"
        assert rag_stack_container_name("ragtest", RAG_ROLE_MODEL) == "ragtest-model"

    def test_generated_base_puts_role_after_ramalama(self) -> None:
        base, generated = rag_stack_base_name(None)
        unique = base.removeprefix("ramalama-")
        assert rag_stack_container_name(base, RAG_ROLE_DOCLING, generated=generated) == f"ramalama-docling-{unique}"
        assert rag_stack_container_name(base, RAG_ROLE_EMBEDDING, generated=generated) == f"ramalama-embedding-{unique}"
        caption = rag_stack_container_name(base, RAG_ROLE_CAPTIONING, generated=generated)
        assert caption == f"ramalama-captioning-{unique}"
        assert rag_stack_container_name(base, RAG_ROLE_MODEL, generated=generated) == f"ramalama-model-{unique}"

    def test_explicit_ramalama_prefix_with_ten_alnum_keeps_user_form(self) -> None:
        name = "ramalama-abcdefghij"
        base, generated = rag_stack_base_name(name)
        assert base == name
        assert generated is False
        assert rag_stack_container_name(base, RAG_ROLE_EMBEDDING, generated=generated) == f"{name}-embedding"
        assert rag_stack_container_name(base, RAG_ROLE_MODEL, generated=generated) == f"{name}-model"
