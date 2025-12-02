import json

import pytest

from ramalama.chat_providers.base import ChatRequestOptions
from ramalama.chat_providers.openai import OpenAICompletionsChatProvider, OpenAIResponsesChatProvider
from ramalama.chat_utils import ImageURLPart, UserMessage


def build_payload(content):
    return {
        "choices": [
            {
                "delta": {
                    "content": content,
                }
            }
        ]
    }


def make_options(**overrides):
    data = {"model": "test-model", "stream": True}
    data.update(overrides)
    return ChatRequestOptions(**data)


class OpenAICompletionsProviderTests:
    def setup_method(self):
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


class OpenAIResponsesProviderTests:
    def setup_method(self):
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
