import json
from argparse import Namespace
from io import BytesIO
from urllib import error as urllib_error
from urllib import request as urllib_request

import pytest

from ramalama.chat_providers.base import ChatProviderError
from ramalama.cli import _default_model_server_url, models_cli
from ramalama.model_server import (
    ModelServerError,
    ModelServerRedirectHandler,
    list_server_models,
    normalize_server_url,
)
from ramalama.plugins.runtimes.inference.llama_cpp import parse_models_payload


def test_normalize_server_url_strips_v1_suffix():
    assert normalize_server_url("http://127.0.0.1:8080/v1") == (
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8080/v1",
    )


def test_normalize_server_url_adds_v1_suffix():
    assert normalize_server_url("http://127.0.0.1:8080") == (
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8080/v1",
    )


def test_model_server_redirect_handler_allows_same_origin_redirect():
    handler = ModelServerRedirectHandler("https://model.example/v1")
    request = urllib_request.Request(
        "https://model.example/v1/models",
        headers={"Authorization": "Bearer secret"},
        method="GET",
    )

    redirected = handler.redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        "https://model.example/models",
    )

    assert redirected is not None
    assert redirected.full_url == "https://model.example/models"
    assert redirected.get_header("Authorization") == "Bearer secret"


def test_model_server_redirect_handler_rejects_cross_origin_redirect():
    handler = ModelServerRedirectHandler("https://model.example/v1")
    request = urllib_request.Request(
        "https://model.example/v1/models",
        headers={"Authorization": "Bearer secret"},
        method="GET",
    )

    with pytest.raises(urllib_error.HTTPError, match="Unsafe redirect blocked"):
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://other.example/models",
        )


def test_model_server_redirect_handler_rejects_https_downgrade():
    handler = ModelServerRedirectHandler("https://model.example/v1")
    request = urllib_request.Request(
        "https://model.example/v1/models",
        headers={"Authorization": "Bearer secret"},
        method="GET",
    )

    with pytest.raises(urllib_error.HTTPError, match="Unsafe redirect blocked"):
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "http://model.example/models",
        )


def test_parse_models_payload_native_shape():
    payload = {"models": [{"name": "tinyllama"}, {"model": "granite"}]}
    assert parse_models_payload(payload) == ["tinyllama", "granite"]


def test_parse_models_payload_openai_shape():
    payload = {"object": "list", "data": [{"id": "tinyllama"}, {"id": "granite"}]}
    assert parse_models_payload(payload) == ["tinyllama", "granite"]


def test_default_model_server_url_ipv6(monkeypatch):
    monkeypatch.setattr(
        "ramalama.cli.ActiveConfig",
        lambda: Namespace(host="::1", port="9090", api_key=None),
    )
    assert _default_model_server_url() == "http://[::1]:9090"


def test_list_server_models_openai(monkeypatch):
    monkeypatch.setattr(
        "ramalama.model_server.OpenAICompletionsChatProvider.list_models",
        lambda self, opener=None: ["tinyllama"],
    )
    assert list_server_models("http://127.0.0.1:8080") == ["tinyllama"]


def test_list_server_models_uses_safe_redirect_handler_with_api_key(monkeypatch):
    captured = {}

    class FakeOpener:
        pass

    def fake_build_opener(handler):
        captured["handler"] = handler
        return FakeOpener()

    def fake_list_models(self, opener=None):
        captured["opener"] = opener
        return ["tinyllama"]

    monkeypatch.setattr(
        "ramalama.model_server.urllib_request.build_opener",
        fake_build_opener,
    )
    monkeypatch.setattr(
        "ramalama.model_server.OpenAICompletionsChatProvider.list_models",
        fake_list_models,
    )

    assert list_server_models(
        "https://model.example",
        api_key="secret",
    ) == ["tinyllama"]

    assert isinstance(captured["handler"], ModelServerRedirectHandler)
    assert captured["opener"] is not None


def test_list_server_models_uses_safe_redirect_handler_for_fallback_with_api_key(monkeypatch):
    captured = {}

    def raise_chat_error(self, opener=None):
        raise ChatProviderError("openai failed")

    class FakeOpener:
        def open(self, request, timeout=10):
            captured["timeout"] = timeout
            return _mock_urlopen_response(json.dumps({"models": [{"name": "fallback-model"}]}).encode())

    def fake_build_opener(handler):
        captured["handler"] = handler
        captured["opener"] = FakeOpener()
        return captured["opener"]

    monkeypatch.setattr(
        "ramalama.model_server.OpenAICompletionsChatProvider.list_models",
        raise_chat_error,
    )
    monkeypatch.setattr(
        "ramalama.model_server.urllib_request.build_opener",
        fake_build_opener,
    )

    assert list_server_models(
        "https://model.example",
        api_key="secret",
    ) == ["fallback-model"]

    assert isinstance(captured["handler"], ModelServerRedirectHandler)
    assert captured["timeout"] == 10


def _mock_urlopen_response(body: bytes, status: int = 200):
    class MockResponse:
        def __init__(self):
            self.status = status

        def read(self):
            return body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    return MockResponse()


def test_list_server_models_llama_cpp_fallback(monkeypatch):
    def raise_chat_error(self, opener=None):
        raise ChatProviderError("openai failed")

    monkeypatch.setattr(
        "ramalama.model_server.OpenAICompletionsChatProvider.list_models",
        raise_chat_error,
    )
    monkeypatch.setattr(
        "ramalama.model_server.urllib_request.urlopen",
        lambda request, timeout=10: _mock_urlopen_response(json.dumps({"models": [{"name": "router-model"}]}).encode()),
    )
    assert list_server_models("http://127.0.0.1:8080") == ["router-model"]


def test_list_server_models_reports_connection_error(monkeypatch):
    from urllib import error as urllib_error

    def raise_chat_error(self, opener=None):
        raise urllib_error.URLError("connection refused")

    monkeypatch.setattr(
        "ramalama.model_server.OpenAICompletionsChatProvider.list_models",
        raise_chat_error,
    )

    with pytest.raises(ModelServerError, match="Could not connect"):
        list_server_models("http://127.0.0.1:8080")


def test_list_server_models_http_error_fallback(monkeypatch):
    from urllib import error as urllib_error

    def raise_http_error(self, opener=None):
        raise urllib_error.HTTPError(
            "http://127.0.0.1:8080/v1/models",
            404,
            "Not Found",
            {},
            BytesIO(b""),
        )

    monkeypatch.setattr(
        "ramalama.model_server.OpenAICompletionsChatProvider.list_models",
        raise_http_error,
    )
    monkeypatch.setattr(
        "ramalama.model_server.urllib_request.urlopen",
        lambda request, timeout=10: _mock_urlopen_response(
            json.dumps({"models": [{"name": "fallback-model"}]}).encode()
        ),
    )
    assert list_server_models("http://127.0.0.1:8080") == ["fallback-model"]


def test_models_cli_prints_models(capsys, monkeypatch):
    monkeypatch.setattr(
        "ramalama.model_server.list_server_models",
        lambda url, api_key=None: ["tinyllama", "granite"],
    )
    models_cli(Namespace(url="http://127.0.0.1:8080", api_key=None, json=False))
    assert capsys.readouterr().out == "tinyllama\ngranite\n"


def test_models_cli_json_output(capsys, monkeypatch):
    monkeypatch.setattr(
        "ramalama.model_server.list_server_models",
        lambda url, api_key=None: ["tinyllama"],
    )
    models_cli(Namespace(url="http://127.0.0.1:8080", api_key=None, json=True))
    assert capsys.readouterr().out == '["tinyllama"]\n'


def test_models_cli_reports_server_error(monkeypatch):
    monkeypatch.setattr(
        "ramalama.model_server.list_server_models",
        lambda url, api_key=None: (_ for _ in ()).throw(ModelServerError("server unavailable")),
    )
    with pytest.raises(SystemExit) as exc:
        models_cli(Namespace(url="http://127.0.0.1:8080", api_key=None, json=False))
    assert exc.value.code == 1
