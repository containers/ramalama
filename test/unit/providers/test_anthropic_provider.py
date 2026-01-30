from unittest.mock import MagicMock, patch

import pytest

from ramalama.chat_providers.anthropic import AnthropicChatProvider, message_to_anthropic_dict
from ramalama.chat_providers.base import ChatRequestOptions
from ramalama.chat_utils import AssistantMessage, ImageURLPart, SystemMessage, ToolCall, ToolMessage, UserMessage


def make_options(**overrides):
    data = {"model": "claude-sonnet-4-20250514", "stream": True}
    data.update(overrides)
    return ChatRequestOptions(**data)


class TestAnthropicProvider:
    def setup_method(self):
        self.provider = AnthropicChatProvider("https://api.anthropic.com")

    def test_auth_headers_uses_x_api_key(self):
        provider = AnthropicChatProvider("https://api.anthropic.com", api_key="sk-ant-test")
        headers = provider.auth_headers()

        assert headers["x-api-key"] == "sk-ant-test"
        assert headers["anthropic-version"] == "2023-06-01"
        assert "Authorization" not in headers

    def test_auth_headers_always_includes_version(self):
        provider = AnthropicChatProvider("https://api.anthropic.com", api_key="test-key")
        headers = provider.auth_headers()

        assert headers["anthropic-version"] == "2023-06-01"

    def test_serializes_user_message(self):
        message = UserMessage(text="Hello, Claude!")

        payload = self.provider.build_payload([message], make_options())

        assert payload["messages"][0]["role"] == "user"
        assert payload["messages"][0]["content"] == [{"type": "text", "text": "Hello, Claude!"}]

    def test_serializes_user_message_with_image_url(self):
        message = UserMessage(
            text="What's in this image?",
            attachments=[ImageURLPart(url="https://example.com/image.png")],
        )

        payload = self.provider.build_payload([message], make_options())
        content = payload["messages"][0]["content"]

        assert content[0] == {"type": "image", "source": {"type": "url", "url": "https://example.com/image.png"}}
        assert content[1] == {"type": "text", "text": "What's in this image?"}

    def test_extracts_system_message_to_top_level(self):
        messages = [
            SystemMessage(text="You are a helpful assistant."),
            UserMessage(text="Hello!"),
        ]

        payload = self.provider.build_payload(messages, make_options())

        assert payload["system"] == "You are a helpful assistant."
        assert len(payload["messages"]) == 1
        assert payload["messages"][0]["role"] == "user"

    def test_requires_model(self):
        message = UserMessage(text="Hello")

        with pytest.raises(ValueError, match="require a model"):
            self.provider.build_payload([message], ChatRequestOptions(model=None))

    def test_default_max_tokens(self):
        message = UserMessage(text="Hello")

        payload = self.provider.build_payload([message], make_options(max_tokens=None))

        assert payload["max_tokens"] == 4096

    def test_custom_max_tokens(self):
        message = UserMessage(text="Hello")

        payload = self.provider.build_payload([message], make_options(max_tokens=1024))

        assert payload["max_tokens"] == 1024

    def test_serializes_assistant_message_with_tool_use(self):
        tool_call = ToolCall(id="toolu_01", name="get_weather", arguments={"location": "NYC"})
        assistant = AssistantMessage(text="Let me check the weather.", tool_calls=[tool_call])

        result = message_to_anthropic_dict(assistant)

        assert result["role"] == "assistant"
        assert result["content"][0] == {"type": "text", "text": "Let me check the weather."}
        assert result["content"][1] == {
            "type": "tool_use",
            "id": "toolu_01",
            "name": "get_weather",
            "input": {"location": "NYC"},
        }

    def test_serializes_tool_message_as_user_with_tool_result(self):
        tool_reply = ToolMessage(text="72°F and sunny", tool_call_id="toolu_01")

        result = message_to_anthropic_dict(tool_reply)

        assert result["role"] == "user"
        assert result["content"] == [{"type": "tool_result", "tool_use_id": "toolu_01", "content": "72°F and sunny"}]

    def test_merges_consecutive_user_messages(self):
        assistant = AssistantMessage(tool_calls=[ToolCall(id="toolu_01", name="search", arguments={"q": "test"})])
        tool_reply = ToolMessage(text="Result", tool_call_id="toolu_01")
        followup = UserMessage(text="Thanks!")

        payload = self.provider.build_payload([assistant, tool_reply, followup], make_options())

        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "assistant"
        assert payload["messages"][1]["role"] == "user"
        assert len(payload["messages"][1]["content"]) == 2
        assert payload["messages"][1]["content"][0]["type"] == "tool_result"
        assert payload["messages"][1]["content"][1]["type"] == "text"

    def test_streaming_parses_content_block_delta(self):
        chunk = (
            b'event: content_block_delta\n'
            b'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello"}}\n'
        )

        events = list(self.provider.parse_stream_chunk(chunk))

        assert len(events) == 1
        assert events[0].text == "Hello"

    def test_streaming_parses_message_stop(self):
        chunk = b'event: message_stop\ndata: {"type":"message_stop"}\n'

        events = list(self.provider.parse_stream_chunk(chunk))

        assert len(events) == 1
        assert events[0].done is True

    def test_streaming_ignores_other_event_types(self):
        chunk = b'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_01"}}\n'

        events = list(self.provider.parse_stream_chunk(chunk))

        assert events == []

    def test_streaming_ignores_invalid_json(self):
        chunk = b"data: {invalid-json\n"

        events = list(self.provider.parse_stream_chunk(chunk))

        assert events == []

    def test_streaming_handles_multiple_events(self):
        chunk = (
            b'event: content_block_delta\n'
            b'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hi"}}\n'
            b'event: content_block_delta\n'
            b'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":" there"}}\n'
        )

        events = list(self.provider.parse_stream_chunk(chunk))

        assert len(events) == 2
        assert events[0].text == "Hi"
        assert events[1].text == " there"

    def test_list_models_fetches_from_api(self):
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"data": [{"id": "claude-sonnet-4"}, {"id": "claude-opus-4"}]}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            models = self.provider.list_models()

        assert models == ["claude-sonnet-4", "claude-opus-4"]

    def test_provider_attribute(self):
        assert self.provider.provider == "anthropic"

    def test_default_path(self):
        assert self.provider.default_path == "/v1/messages"

    def test_temperature_included_when_set(self):
        message = UserMessage(text="Hello")

        payload = self.provider.build_payload([message], make_options(temperature=0.7))

        assert payload["temperature"] == 0.7

    def test_temperature_omitted_when_none(self):
        message = UserMessage(text="Hello")

        payload = self.provider.build_payload([message], make_options(temperature=None))

        assert "temperature" not in payload
