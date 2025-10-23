"""Unit tests for max_tokens functionality across the ramalama codebase."""

import argparse
from unittest.mock import patch

import pytest

from ramalama.command.context import RamalamaArgsContext
from ramalama.config import default_config


class TestMaxTokensConfig:
    """Test max_tokens configuration defaults and validation."""

    def test_max_tokens_default_value(self):
        """Test that max_tokens has the correct default value."""
        with patch("ramalama.config.load_file_config", return_value={}):
            with patch("ramalama.config.load_env_config", return_value={}):
                cfg = default_config()
                assert cfg.max_tokens == 0

    def test_max_tokens_config_override(self):
        """Test that max_tokens can be overridden in config."""
        file_config = {"max_tokens": 512}

        with patch("ramalama.config.load_file_config", return_value=file_config):
            with patch("ramalama.config.load_env_config", return_value={}):
                cfg = default_config()
                assert cfg.max_tokens == 512

    def test_max_tokens_env_override(self):
        """Test that max_tokens can be set via environment variable."""
        env = {"RAMALAMA_MAX_TOKENS": "1024"}

        with patch("ramalama.config.load_file_config", return_value={}):
            cfg = default_config(env)
            # Environment variables are loaded as strings, need to convert to int
            assert cfg.max_tokens == "1024"  # String value from env
            assert cfg.is_set("max_tokens") is True

    def test_max_tokens_file_config_override(self):
        """Test that max_tokens can be set via file config."""
        file_config = {"max_tokens": 256}

        with patch("ramalama.config.load_file_config", return_value=file_config):
            with patch("ramalama.config.load_env_config", return_value={}):
                cfg = default_config()
                assert cfg.max_tokens == 256
                assert cfg.is_set("max_tokens") is True

    def test_max_tokens_env_overrides_file_config(self):
        """Test that environment variable overrides file config."""
        file_config = {"max_tokens": 256}
        env = {"RAMALAMA_MAX_TOKENS": "1024"}

        with patch("ramalama.config.load_file_config", return_value=file_config):
            cfg = default_config(env)
            # Environment variables are loaded as strings
            assert cfg.max_tokens == "1024"  # env should override file as string

    @pytest.mark.parametrize("value", ["0", "100", "1024", "4096", "0"])
    def test_max_tokens_valid_values(self, value):
        """Test that max_tokens accepts valid integer values."""
        env = {"RAMALAMA_MAX_TOKENS": value}

        with patch("ramalama.config.load_file_config", return_value={}):
            cfg = default_config(env)
            # Environment variables are loaded as strings
            assert cfg.max_tokens == value  # String value from env

    def test_max_tokens_negative_value(self):
        """Test that max_tokens accepts negative values (though they may be treated as 0)."""
        env = {"RAMALAMA_MAX_TOKENS": "-1"}

        with patch("ramalama.config.load_file_config", return_value={}):
            cfg = default_config(env)
            # Environment variables are loaded as strings
            assert cfg.max_tokens == "-1"


class TestMaxTokensCLI:
    """Test CLI argument parsing for max_tokens."""

    def test_max_tokens_cli_argument_parsing(self):
        """Test that --max-tokens argument is properly parsed."""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--max-tokens",
            dest="max_tokens",
            type=int,
            default=0,
            help="maximum number of tokens to generate (0 = unlimited)",
        )

        # Test valid values
        args = parser.parse_args(["--max-tokens", "512"])
        assert args.max_tokens == 512

        args = parser.parse_args(["--max-tokens", "0"])
        assert args.max_tokens == 0

        args = parser.parse_args(["--max-tokens", "1024"])
        assert args.max_tokens == 1024

    def test_max_tokens_cli_default_value(self):
        """Test that --max-tokens has correct default value."""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--max-tokens",
            dest="max_tokens",
            type=int,
            default=0,
            help="maximum number of tokens to generate (0 = unlimited)",
        )

        args = parser.parse_args([])
        assert args.max_tokens == 0

    def test_max_tokens_cli_invalid_value(self):
        """Test that --max-tokens rejects invalid values."""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--max-tokens",
            dest="max_tokens",
            type=int,
            default=0,
            help="maximum number of tokens to generate (0 = unlimited)",
        )

        with pytest.raises(SystemExit):
            parser.parse_args(["--max-tokens", "invalid"])

    def test_max_tokens_cli_negative_value(self):
        """Test that --max-tokens accepts negative values."""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--max-tokens",
            dest="max_tokens",
            type=int,
            default=0,
            help="maximum number of tokens to generate (0 = unlimited)",
        )

        args = parser.parse_args(["--max-tokens", "-1"])
        assert args.max_tokens == -1


class TestMaxTokensContext:
    """Test RamalamaArgsContext max_tokens handling."""

    def test_max_tokens_context_from_argparse(self):
        """Test that max_tokens is properly extracted from argparse namespace."""
        args = argparse.Namespace(max_tokens=512)
        ctx = RamalamaArgsContext.from_argparse(args)

        assert ctx.max_tokens == 512

    def test_max_tokens_context_default_none(self):
        """Test that max_tokens defaults to None when not provided."""
        args = argparse.Namespace()
        ctx = RamalamaArgsContext.from_argparse(args)

        assert ctx.max_tokens is None

    def test_max_tokens_context_zero_value(self):
        """Test that max_tokens can be set to 0."""
        args = argparse.Namespace(max_tokens=0)
        ctx = RamalamaArgsContext.from_argparse(args)

        assert ctx.max_tokens == 0

    def test_max_tokens_context_negative_value(self):
        """Test that max_tokens can be set to negative values."""
        args = argparse.Namespace(max_tokens=-1)
        ctx = RamalamaArgsContext.from_argparse(args)

        assert ctx.max_tokens == -1
