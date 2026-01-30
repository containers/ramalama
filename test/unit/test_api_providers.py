import argparse
from unittest.mock import MagicMock, patch

import pytest

from ramalama.chat_providers.anthropic import AnthropicChatProvider
from ramalama.chat_providers.api_providers import get_chat_provider
from ramalama.chat_providers.openai import OpenAIResponsesChatProvider
from ramalama.cli import run_cli
from ramalama.transports.api import APITransport


def test_get_chat_provider_returns_openai_provider():
    provider = get_chat_provider("openai")

    assert isinstance(provider, OpenAIResponsesChatProvider)
    assert provider.base_url == "https://api.openai.com/v1"
    assert provider.provider == "openai"


def test_get_chat_provider_returns_anthropic_provider():
    provider = get_chat_provider("anthropic")

    assert isinstance(provider, AnthropicChatProvider)
    assert provider.base_url == "https://api.anthropic.com"
    assert provider.provider == "anthropic"


def test_get_chat_provider_raises_for_unknown_scheme():
    with pytest.raises(ValueError):
        get_chat_provider("unknown_provider")


class TestRunCliWithAPITransport:
    """Tests for run_cli handling of API transports."""

    provider = "anthropic"
    model = "claude-sonnet-4-20250514"

    def mock_args(self) -> argparse.Namespace:
        args = argparse.Namespace(
            MODEL=f"{self.provider}://{self.model}",
            store="/tmp/store",
            container=False,
            engine=None,
            rag=None,
            dryrun=False,
            debug=False,
            port="8080",
            pull="newer",
        )
        return args

    def mock_provider(self):
        mock_provider = MagicMock()
        mock_provider.provider = self.provider
        mock_provider.api_key = "test-key"
        mock_provider.list_models.return_value = [self.model]
        return mock_provider

    def mock_transport(self) -> APITransport:
        return APITransport(f"{self.provider}://{self.model}", self.mock_provider())

    def test_run_cli_does_not_assemble_command_for_api_transport(self):
        """Regression test: API transports should not trigger command assembly.

        Command assembly calls _get_entry_model_path() which raises
        NotImplementedError for API transports since they don't have
        local model files.
        """
        transport = self.mock_transport()
        transport.run = MagicMock()
        transport.ensure_model_exists = MagicMock()

        with (
            patch("ramalama.cli.New", return_value=transport),
            patch("ramalama.cli.compute_serving_port", return_value="8080"),
            patch("ramalama.cli.assemble_command_lazy") as mock_assemble,
        ):
            run_cli(self.mock_args())

            assert not mock_assemble.called, "assemble_command should not be called with hosted API providers"
            # run() should be called with an empty command list
            transport.run.assert_called_once()
            call_args = transport.run.call_args[0]
            assert call_args[1] == [], "API transport should receive empty server_cmd"

    def test_run_cli_defaults_url_and_api_key_from_provider(self):
        """If url/api_key are not provided, provider defaults should be used."""
        provider = self.mock_provider()
        provider.base_url = "https://fake.example.com"
        provider.api_key = "fake-api-key"

        transport = APITransport(self.model, provider)
        captured = {}

        def fake_chat(args, provider=None):
            captured["url"] = args.url
            captured["api_key"] = args.api_key
            captured["provider_url"] = provider.base_url
            captured["provider_api_key"] = provider.api_key

        args = self.mock_args()
        args.url = None
        args.api_key = None

        with (
            patch("ramalama.cli.New", return_value=transport),
            patch("ramalama.cli.compute_serving_port", return_value="8080"),
            patch("ramalama.transports.api.chat", side_effect=fake_chat),
        ):
            run_cli(args)

        assert captured["url"] == provider.base_url
        assert captured["api_key"] == provider.api_key
        assert captured["provider_url"] == provider.base_url
        assert captured["provider_api_key"] == provider.api_key

    def test_run_cli_allows_overriding_provider_defaults(self):
        """Explicit url/api_key CLI flags should override provider defaults."""
        provider = self.mock_provider()
        provider.base_url = "https://fake.example.com"
        provider.api_key = "fake-api-key"

        transport = APITransport(self.model, provider)
        captured = {}

        def fake_chat(args, provider=None):
            captured["url"] = args.url
            captured["api_key"] = args.api_key
            captured["provider_url"] = provider.base_url
            captured["provider_api_key"] = provider.api_key

        args = self.mock_args()
        args.url = "https://override.example.com"
        args.api_key = "override-api-key"

        with (
            patch("ramalama.cli.New", return_value=transport),
            patch("ramalama.cli.compute_serving_port", return_value="8080"),
            patch("ramalama.transports.api.chat", side_effect=fake_chat),
        ):
            run_cli(args)

        assert captured["url"] == args.url
        assert captured["api_key"] == args.api_key
        assert captured["provider_url"] == args.url
        assert captured["provider_api_key"] == args.api_key
