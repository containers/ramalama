import json

import pytest

from ramalama.chat_providers.base import ChatRequestOptions
from ramalama.chat_providers.openai import OpenAIChatProvider, OpenAIHostedChatProvider
from ramalama.chat_utils import ChatMessage, ImageURLPart


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


def test_openai_provider_extracts_string_and_structured_deltas():
    provider = OpenAIChatProvider("http://example.com")
    assert provider._extract_delta(build_payload("hello")) == "hello"

    structured = build_payload(
        [
            {"type": "text", "text": "hello"},
            {"type": "output_text", "text": " world"},
        ]
    )
    assert provider._extract_delta(structured) == "hello world"


def test_openai_provider_streaming_handles_structured_chunks():
    provider = OpenAIChatProvider("http://example.com")
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

    events = list(provider.parse_stream_chunk(chunk))

    assert len(events) == 1
    assert events[0].text == "Hi there"


def test_openai_provider_rejects_attachments_in_legacy_mode():
    provider = OpenAIChatProvider("http://example.com")
    message = ChatMessage(role="user", attachments=[ImageURLPart(url="http://img")])

    with pytest.raises(ValueError):
        provider.build_payload([message], make_options())


def test_openai_hosted_provider_serializes_structured_content():
    provider = OpenAIHostedChatProvider("http://example.com")
    message = ChatMessage(
        role="user",
        text="hello",
        attachments=[ImageURLPart(url="http://img", detail="high")],
    )

    payload = provider.build_payload([message], make_options(max_tokens=128))
    serialized = payload["messages"][0]["content"]

    assert serialized[0] == {"type": "text", "text": "hello"}
    assert serialized[1]["type"] == "image_url"
    assert serialized[1]["image_url"] == {"url": "http://img", "detail": "high"}
    assert payload["max_completion_tokens"] == 128
    assert "max_tokens" not in payload
