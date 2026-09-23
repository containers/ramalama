"""Unit tests for the API key handling shared by the RAG container scripts.

``is_authorized`` is the only part of a keyed RAG pipeline that *decides*
anything rather than just presenting a key, so it is the security boundary the
whole feature rests on. It lives in its own third-party-free module precisely
so these tests can import it: rag_framework, the one caller that listens on a
port, pulls in fastapi, aiohttp, openai, qdrant_client and uvicorn at module
scope and none of those are test dependencies.
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "container-images" / "scripts"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


auth = _load(SCRIPTS / "ramalama_api_auth.py", "ramalama_api_auth")


class TestUnauthenticatedByDefault:
    def test_no_key_accepts_anything(self):
        assert auth.is_authorized("", authorization="Bearer whatever")
        assert auth.is_authorized("", x_api_key="whatever")
        assert auth.is_authorized("")


class TestAcceptsValidCredentials:
    def test_bearer_header(self):
        assert auth.is_authorized("sekret", authorization="Bearer sekret")

    def test_bearer_scheme_is_case_insensitive(self):
        assert auth.is_authorized("sekret", authorization="bearer sekret")

    def test_x_api_key_header(self):
        assert auth.is_authorized("sekret", x_api_key="sekret")


class TestRejectsEverythingElse:
    @pytest.mark.parametrize(
        "headers",
        [
            pytest.param({}, id="no credentials"),
            pytest.param({"authorization": "Bearer wrong"}, id="wrong bearer token"),
            pytest.param({"authorization": "Bearer "}, id="empty bearer token"),
            pytest.param({"authorization": "Bearer"}, id="bearer with no token"),
            pytest.param({"authorization": "sekret"}, id="raw key with no scheme"),
            pytest.param({"authorization": "Basic sekret"}, id="wrong scheme"),
            pytest.param({"x_api_key": "wrong"}, id="wrong x-api-key"),
            pytest.param({"authorization": "Bearer sekre"}, id="prefix of the key"),
            pytest.param({"authorization": "Bearer sekrett"}, id="key plus a suffix"),
        ],
    )
    def test_rejected(self, headers):
        assert not auth.is_authorized("sekret", **headers)

    def test_a_bearer_header_does_not_fall_back_to_x_api_key(self):
        """A client that picked the bearer form is held to it, as llama.cpp does."""
        assert not auth.is_authorized("sekret", authorization="Bearer wrong", x_api_key="sekret")


class TestNonAsciiCredentials:
    """secrets.compare_digest raises TypeError on non-ASCII str, which would answer 500."""

    def test_non_ascii_token_is_rejected_not_fatal(self):
        assert not auth.is_authorized("sekret", authorization="Bearer café")

    def test_non_ascii_key_still_matches(self):
        # Headers reach us latin-1 decoded, so this is what a client sending the
        # UTF-8 bytes of "sekrét" looks like by the time is_authorized sees it.
        wire = "sekrét".encode("utf-8").decode("latin-1")
        assert auth.is_authorized("sekrét", authorization=f"Bearer {wire}")

    def test_non_ascii_key_rejects_a_wrong_token(self):
        assert not auth.is_authorized("sekrét", authorization="Bearer sekret")


class TestBearerHeader:
    """Both scripts present the key upstream to the llama.cpp servers."""

    def test_no_key_presents_nothing(self):
        assert auth.bearer_header("") == {}

    def test_key_is_presented_as_bearer(self):
        assert auth.bearer_header("sekret") == {"Authorization": "Bearer sekret"}


class TestScriptsUseTheSharedModule:
    """Guards against the key handling being re-inlined where nothing can test it."""

    @pytest.mark.parametrize(
        "script,expected",
        [
            ("rag_framework", ("bearer_header", "is_authorized")),
            ("doc2rag", ("bearer_header",)),
        ],
    )
    def test_imports_what_it_needs(self, script, expected):
        source = (SCRIPTS / script).read_text(encoding="utf-8")
        assert f"from ramalama_api_auth import {', '.join(expected)}" in source
