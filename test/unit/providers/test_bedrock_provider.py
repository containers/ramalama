import json

import pytest

from ramalama.chat_providers.base import ChatRequestOptions
from ramalama.chat_providers.bedrock import BedrockChatProvider
from ramalama.chat_utils import AssistantMessage, ImageBytesPart, SystemMessage, ToolCall, ToolMessage, UserMessage


def make_options(**overrides):
    data = {"model": "nvidia.nemotron-nano-12b-v2", "stream": True}
    data.update(overrides)
    return ChatRequestOptions(**data)


def make_provider():
    return BedrockChatProvider(
        base_url="https://bedrock-runtime.us-east-1.amazonaws.com",
        region="us-east-1",
        access_key_id="AKIA_TEST",
        secret_access_key="SECRET_TEST",
    )


def test_build_payload_with_system_and_inference_config():
    provider = make_provider()
    system = SystemMessage(text="system rules")
    user = UserMessage(text="hello")

    payload = provider.build_payload([system, user], make_options(max_tokens=64, temperature=0.2))

    assert payload["system"] == [{"text": "system rules"}]
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][0]["content"] == [{"text": "hello"}]
    assert payload["inferenceConfig"]["maxTokens"] == 64
    assert payload["inferenceConfig"]["temperature"] == 0.2


def test_build_payload_rejects_tool_messages_and_calls():
    provider = make_provider()
    tool_call = ToolCall(id="tool-1", name="lookup", arguments={"query": "hi"})
    assistant = AssistantMessage(tool_calls=[tool_call])
    tool_reply = ToolMessage(text="result", tool_call_id="tool-1")

    with pytest.raises(ValueError):
        provider.build_payload([assistant, tool_reply], make_options())


def test_build_payload_rejects_attachments():
    provider = make_provider()
    user = UserMessage(text="hello", attachments=[ImageBytesPart(data=b"\x00\x01")])

    with pytest.raises(ValueError):
        provider.build_payload([user], make_options())


def test_parse_stream_chunk_extracts_text_and_done():
    provider = make_provider()
    payload = {
        "output": {
            "message": {
                "content": [
                    {"text": "Hi"},
                    {"text": " there"},
                ]
            }
        }
    }
    chunk = json.dumps(payload).encode("utf-8")

    events = list(provider.parse_stream_chunk(chunk))

    assert len(events) == 2
    assert events[0].text == "Hi there"
    assert events[1].done is True


def test_parse_stream_chunk_ignores_partial_json():
    provider = make_provider()
    events = list(provider.parse_stream_chunk(b'{"output":'))

    assert events == []


def test_list_models_parses_response(monkeypatch):
    provider = make_provider()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"modelSummaries": [{"modelId": "m1"}, {"modelId": "m2"}]}).encode("utf-8")

    def fake_urlopen(request):
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert provider.list_models() == ["m1", "m2"]


def test_resolve_request_path_encodes_inference_profile_arn():
    provider = make_provider()
    arn = "arn:aws:bedrock:us-east-1:123456789012:inference-profile/test/profile"
    options = make_options(model=arn)

    path = provider.resolve_request_path(options)

    assert path == (
        "/model/arn%3Aaws%3Abedrock%3Aus-east-1%3A123456789012%3A" "inference-profile%2Ftest%2Fprofile/converse"
    )
