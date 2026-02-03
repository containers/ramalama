import json

import pytest

from ramalama.chat_providers.base import ChatRequestOptions
from ramalama.chat_providers.gemini import GeminiChatProvider
from ramalama.chat_utils import (
    AssistantMessage,
    ImageBytesPart,
    ImageURLPart,
    SystemMessage,
    ToolCall,
    ToolMessage,
    UserMessage,
)


def make_options(**overrides):
    data = {"model": "gemini-1.5-flash", "stream": True}
    data.update(overrides)
    return ChatRequestOptions(**data)


def test_build_payload_with_system_and_images():
    provider = GeminiChatProvider("http://example.com")
    system = SystemMessage(text="system rules")
    user = UserMessage(text="hello", attachments=[ImageBytesPart(data=b"\x01\x02", mime_type="image/png")])

    payload = provider.build_payload([system, user], make_options(max_tokens=64, temperature=0.2))

    assert payload["system_instruction"]["parts"][0]["text"] == "system rules"
    assert payload["contents"][0]["role"] == "user"
    parts = payload["contents"][0]["parts"]
    assert parts[0] == {"text": "hello"}
    assert parts[1]["inline_data"]["mime_type"] == "image/png"
    assert parts[1]["inline_data"]["data"] == "AQI="
    assert payload["generation_config"]["max_output_tokens"] == 64
    assert payload["generation_config"]["temperature"] == 0.2


def test_build_payload_accepts_data_url_images():
    provider = GeminiChatProvider("http://example.com")
    user = UserMessage(attachments=[ImageURLPart(url="data:image/png;base64,AQI=")])

    payload = provider.build_payload([user], make_options())

    parts = payload["contents"][0]["parts"]
    assert parts[0]["inline_data"]["mime_type"] == "image/png"
    assert parts[0]["inline_data"]["data"] == "AQI="


def test_build_payload_rejects_non_data_url_images():
    provider = GeminiChatProvider("http://example.com")
    user = UserMessage(attachments=[ImageURLPart(url="http://example.com/image.png")])

    with pytest.raises(ValueError):
        provider.build_payload([user], make_options())


def test_build_payload_rejects_tool_calls():
    provider = GeminiChatProvider("http://example.com")
    tool_call = ToolCall(id="call-1", name="lookup", arguments={"query": "weather"})
    assistant = AssistantMessage(tool_calls=[tool_call])
    tool_reply = ToolMessage(text="result", tool_call_id="call-1")

    with pytest.raises(ValueError):
        provider.build_payload([assistant, tool_reply], make_options())


def test_parse_stream_chunk_extracts_text():
    provider = GeminiChatProvider("http://example.com")
    payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "Hi"},
                        {"text": " there"},
                    ]
                }
            }
        ]
    }
    chunk = b"data: " + json.dumps(payload).encode("utf-8") + b"\n\n"

    events = list(provider.parse_stream_chunk(chunk))

    assert len(events) == 1
    assert events[0].text == "Hi there"


def test_list_models_parses_response(monkeypatch):
    provider = GeminiChatProvider("http://example.com", api_key="secret")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {"models": [{"name": "models/gemini-1.5-flash"}, {"name": "models/gemini-1.5-pro"}]}
            ).encode("utf-8")

    def fake_urlopen(request):
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert provider.list_models() == ["gemini-1.5-flash", "gemini-1.5-pro"]
