import io
import urllib.error

import pytest

import ramalama.chat_providers.base as base_module
from ramalama.chat_providers.base import ChatProviderError
from ramalama.chat_providers.openai import OpenAIResponsesChatProvider


def test_list_models_reports_auth_error(monkeypatch):
    provider = OpenAIResponsesChatProvider("https://api.openai.com/v1", api_key="bad")
    error_body = b'{"error":{"message":"Invalid API key"}}'
    http_error = urllib.error.HTTPError(
        provider.build_url("/models"),
        401,
        "Unauthorized",
        {},
        io.BytesIO(error_body),
    )

    def fake_urlopen(request):
        raise http_error

    monkeypatch.setattr(base_module.urllib_request, "urlopen", fake_urlopen)

    with pytest.raises(ChatProviderError) as excinfo:
        provider.list_models()

    message = str(excinfo.value)
    assert "Could not authenticate with openai." in message
    assert "missing or invalid" in message
    assert "Invalid API key" in message
