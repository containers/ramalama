import json
from typing import Any

import pytest

from ramalama.chat_providers.base import ChatRequestOptions
from ramalama.chat_providers.openai import OpenAICompletionsChatProvider, OpenAIResponsesChatProvider
from ramalama.chat_utils import AssistantMessage, ImageURLPart, SystemMessage, ToolCall, ToolMessage, UserMessage


def build_payload(content: Any) -> dict[str, Any]:
    return {
        "choices": [
            {
                "delta": {
                    "content": content,
                }
            }
        ]
    }


def make_options(**overrides: Any) -> ChatRequestOptions:
    return ChatRequestOptions(model="test-model", stream=True, **overrides)


class TestOpenAICompletionsProvider:
    provider: OpenAICompletionsChatProvider

    def setup_method(self) -> None:
        self.provider = OpenAICompletionsChatProvider("http://example.com")

    def test_extracts_string_and_structured_deltas(self):
        assert self.provider._extract_delta(build_payload("hello")) == "hello"

        structured = build_payload(
            [
                {"type": "text", "text": "hello"},
                {"type": "output_text", "text": " world"},
            ]
        )
        assert self.provider._extract_delta(structured) == "hello world"

    def test_streaming_handles_structured_chunks(self):
        chunk = (
            b"data: "
            + json.dumps(
                build_payload(
                    [
                        {"type": "output_text", "text": "Hi"},
                        {"type": "output_text", "text": " there"},
                    ]
                )
            ).encode("utf-8")
            + b"\n\n"
        )

        events = list(self.provider.parse_stream_chunk(chunk))

        assert len(events) == 1
        assert events[0].text == "Hi there"

    def test_rejects_attachments(self):
        message = UserMessage(attachments=[ImageURLPart(url="http://img")])

        with pytest.raises(ValueError):
            self.provider.build_payload([message], make_options())

    def test_rejects_assistant_attachments(self):
        message = AssistantMessage(text="hello", attachments=[ImageURLPart(url="http://img")])

        with pytest.raises(ValueError):
            self.provider.build_payload([message], make_options())

    def test_serializes_system_message(self):
        payload = self.provider.build_payload([SystemMessage(text="You are helpful.")], make_options())
        assert payload["messages"][0] == {"role": "system", "content": "You are helpful."}

    def test_serializes_tool_calls_and_responses(self):
        tool_call = ToolCall(id="call-1", name="lookup", arguments={"query": "weather"})
        assistant = AssistantMessage(tool_calls=[tool_call])
        tool_reply = ToolMessage(text="72F and sunny", tool_call_id="call-1")

        payload = self.provider.build_payload([assistant, tool_reply], make_options())
        messages = payload["messages"]

        assert messages[0]["tool_calls"][0]["function"]["name"] == "lookup"
        assert messages[0]["tool_calls"][0]["function"]["arguments"] == '{"query": "weather"}'
        assert messages[1]["tool_call_id"] == "call-1"

    def test_omits_empty_tool_calls(self):
        assistant = AssistantMessage(text="Hello")

        payload = self.provider.build_payload([assistant], make_options())

        assert "tool_calls" not in payload["messages"][0]


class TestOpenAIResponsesProvider:
    provider: OpenAIResponsesChatProvider

    def setup_method(self) -> None:
        self.provider = OpenAIResponsesChatProvider("http://example.com")

    def test_serializes_structured_content(self):
        message = UserMessage(
            text="hello",
            attachments=[ImageURLPart(url="http://img", detail="high")],
        )

        payload = self.provider.build_payload([message], make_options(max_tokens=128))
        serialized = payload["input"][0]["content"]

        assert serialized[0] == {"type": "input_text", "text": "hello"}
        assert serialized[1]["type"] == "image_url"
        assert serialized[1]["image_url"] == {"url": "http://img", "detail": "high"}
        assert payload["max_completion_tokens"] == 128
        assert "max_tokens" not in payload
        assert "max_completion_tokens" in payload

    def test_serializes_attachments_without_text(self):
        message = UserMessage(text=None, attachments=[ImageURLPart(url="http://img")])

        payload = self.provider.build_payload([message], make_options())
        serialized = payload["input"][0]["content"]

        assert serialized == [{"type": "image_url", "image_url": {"url": "http://img"}}]

    def test_omits_max_completion_tokens_for_non_positive_values(self):
        payload = self.provider.build_payload([UserMessage(text="hello")], make_options(max_tokens=0))

        assert "max_completion_tokens" not in payload

    def test_streaming_emits_delta_and_completion_events(self):
        chunk = (
            b"event: response.output_text.delta\n"
            b'data: {"type":"response.output_text.delta","delta":{"text":"Hi"}}\n\n'
            b"event: response.completed\n"
            b'data: {"type":"response.completed"}\n\n'
        )

        events = list(self.provider.parse_stream_chunk(chunk))

        assert events[0].text == "Hi"
        assert events[1].done is True

    def test_serializes_tool_calls(self):
        tool_call = ToolCall(id="call-9", name="lookup", arguments={"city": "NYC"})
        assistant = AssistantMessage(tool_calls=[tool_call])
        tool_reply = ToolMessage(text="Clear skies", tool_call_id="call-9")

        payload = self.provider.build_payload([assistant, tool_reply], make_options())
        first_input = payload["input"][0]

        assert first_input["tool_calls"][0]["function"]["name"] == "lookup"
        assert first_input["tool_calls"][0]["function"]["arguments"] == '{"city": "NYC"}'
        assert payload["input"][1]["tool_call_id"] == "call-9"

    def test_omits_empty_tool_calls(self):
        assistant = AssistantMessage(text="Hello")

        payload = self.provider.build_payload([assistant], make_options())

        assert "tool_calls" not in payload["input"][0]

    def test_streaming_emits_done_event_for_done_marker(self):
        events = list(self.provider.parse_stream_chunk(b"data: [DONE]\n\n"))

        assert len(events) == 1
        assert events[0].done is True

    def test_streaming_ignores_invalid_json_chunks(self):
        events = list(self.provider.parse_stream_chunk(b"data: {invalid-json\n\n"))

        assert events == []

    def test_streaming_extracts_text_from_done_events(self):
        chunk = (
            b"event: response.output_text.done\n"
            b'data: {"type":"response.output_text.done","output":[{"content":'
            b'[{"type":"output_text","text":"All done"}]}]}\n\n'
        )

        events = list(self.provider.parse_stream_chunk(chunk))

        assert len(events) == 1
        assert events[0].text == "All done"
