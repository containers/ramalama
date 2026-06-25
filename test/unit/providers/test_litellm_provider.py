import json

from ramalama.chat_providers.base import ChatRequestOptions
from ramalama.chat_providers.litellm import LiteLLMChatProvider
from ramalama.chat_utils import SystemMessage, UserMessage


def make_options(**overrides):
    data = {"model": "anthropic/claude-sonnet-4-6", "stream": True}
    data.update(overrides)
    return ChatRequestOptions(**data)


class TestLiteLLMProvider:
    def setup_method(self):
        self.provider = LiteLLMChatProvider("http://localhost:4000")

    def test_provider_name(self):
        assert self.provider.provider == "litellm"

    def test_base_url(self):
        assert self.provider.base_url == "http://localhost:4000"

    def test_default_path(self):
        assert self.provider.default_path == "/chat/completions"

    def test_build_url(self):
        assert self.provider.build_url() == "http://localhost:4000/chat/completions"

    def test_build_payload(self):
        messages = [
            SystemMessage(text="You are helpful."),
            UserMessage(text="Hello"),
        ]
        options = make_options()
        payload = self.provider.build_payload(messages, options)

        assert payload["stream"] is True
        assert payload["model"] == "anthropic/claude-sonnet-4-6"
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"

    def test_auth_headers_with_key(self):
        provider = LiteLLMChatProvider("http://localhost:4000", api_key="sk-test")
        headers = provider.auth_headers()
        assert headers["Authorization"] == "Bearer sk-test"

    def test_auth_headers_without_key(self):
        provider = LiteLLMChatProvider("http://localhost:4000", api_key=None)
        headers = provider.auth_headers()
        assert headers == {}

    def test_parse_stream_chunk(self):
        chunk_data = {
            "choices": [{"delta": {"content": "Hello from LiteLLM"}}]
        }
        chunk = b"data: " + json.dumps(chunk_data).encode("utf-8") + b"\n\n"
        events = list(self.provider.parse_stream_chunk(chunk))

        assert len(events) == 1
        assert events[0].text == "Hello from LiteLLM"

    def test_parse_stream_done(self):
        chunk = b"data: [DONE]\n\n"
        events = list(self.provider.parse_stream_chunk(chunk))

        assert len(events) == 1
        assert events[0].done is True

    def test_create_request(self):
        messages = [UserMessage(text="Hi")]
        options = make_options()
        request = self.provider.create_request(messages, options)

        assert request.full_url == "http://localhost:4000/chat/completions"
        assert request.method == "POST"
        body = json.loads(request.data)
        assert body["messages"][0]["content"] == "Hi"
