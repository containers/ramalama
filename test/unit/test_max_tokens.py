"""Unit tests for max_tokens functionality across the ramalama codebase."""

import argparse
from unittest.mock import Mock, patch

import pytest

from ramalama.command.context import RamalamaArgsContext
from ramalama.config import default_config
from ramalama.daemon.service.command_factory import CommandFactory


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


class TestMaxTokensCommandFactory:
    """Test CommandFactory max_tokens parameter handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_model = Mock()
        self.mock_model._get_entry_model_path.return_value = "/test/model/path"
        self.mock_model._get_mmproj_path.return_value = None
        self.mock_model._get_chat_template_path.return_value = None
        self.mock_model.model_name = "test_model"

    @patch('ramalama.daemon.service.command_factory.CONFIG')
    def test_command_factory_max_tokens_default(self, mock_config):
        """Test that CommandFactory uses default max_tokens when not provided."""
        mock_config.max_tokens = 0

        request_args = {
            "ctx_size": 2048,
            "temp": "0.8",
            "ngl": -1,
            "threads": 4,
            "runtime_args": [],
            "debug": False,
            "webui": "",
            "thinking": False,
            "seed": "",
        }

        factory = CommandFactory(self.mock_model, "llama.cpp", 8080, "/tmp/log", request_args)

        # Call _set_defaults to set the default values
        factory._set_defaults()

        # max_tokens should be set to default (0) when not provided
        assert factory.request_args["max_tokens"] == 0

    def test_command_factory_max_tokens_provided(self):
        """Test that CommandFactory uses provided max_tokens value."""
        request_args = {
            "max_tokens": 512,
            "ctx_size": 2048,
            "temp": "0.8",
            "ngl": -1,
            "threads": 4,
            "runtime_args": [],
            "debug": False,
            "webui": "",
            "thinking": False,
            "seed": "",
        }

        factory = CommandFactory(self.mock_model, "llama.cpp", 8080, "/tmp/log", request_args)

        assert factory.request_args["max_tokens"] == 512

    @patch('ramalama.daemon.service.command_factory.check_nvidia')
    @patch('ramalama.daemon.service.command_factory.check_metal')
    def test_llama_serve_command_with_max_tokens(self, mock_check_metal, mock_check_nvidia):
        """Test that llama serve command includes -n parameter when max_tokens > 0."""
        mock_check_nvidia.return_value = False
        mock_check_metal.return_value = False

        request_args = {
            "max_tokens": 512,
            "ctx_size": 2048,
            "temp": "0.8",
            "ngl": -1,
            "threads": 4,
            "runtime_args": [],
            "debug": False,
            "webui": "",
            "thinking": False,
            "seed": "",
        }

        factory = CommandFactory(self.mock_model, "llama.cpp", 8080, "/tmp/log", request_args)
        cmd = factory._build_llama_serve_command()

        # Check that -n parameter is added with correct value
        assert "-n" in cmd
        n_index = cmd.index("-n")
        assert cmd[n_index + 1] == "512"

    @patch('ramalama.daemon.service.command_factory.check_nvidia')
    @patch('ramalama.daemon.service.command_factory.check_metal')
    def test_llama_serve_command_no_max_tokens_when_zero(self, mock_check_metal, mock_check_nvidia):
        """Test that llama serve command doesn't include -n parameter when max_tokens is 0."""
        mock_check_nvidia.return_value = False
        mock_check_metal.return_value = False

        request_args = {
            "max_tokens": 0,
            "ctx_size": 2048,
            "temp": "0.8",
            "ngl": -1,
            "threads": 4,
            "runtime_args": [],
            "debug": False,
            "webui": "",
            "thinking": False,
            "seed": "",
        }

        factory = CommandFactory(self.mock_model, "llama.cpp", 8080, "/tmp/log", request_args)
        cmd = factory._build_llama_serve_command()

        # Check that -n parameter is not added
        assert "-n" not in cmd

    @patch('ramalama.daemon.service.command_factory.check_nvidia')
    @patch('ramalama.daemon.service.command_factory.check_metal')
    def test_llama_serve_command_negative_max_tokens(self, mock_check_metal, mock_check_nvidia):
        """Test that llama serve command doesn't include -n parameter when max_tokens is negative."""
        mock_check_nvidia.return_value = False
        mock_check_metal.return_value = False

        request_args = {
            "max_tokens": -1,
            "ctx_size": 2048,
            "temp": "0.8",
            "ngl": -1,
            "threads": 4,
            "runtime_args": [],
            "debug": False,
            "webui": "",
            "thinking": False,
            "seed": "",
        }

        factory = CommandFactory(self.mock_model, "llama.cpp", 8080, "/tmp/log", request_args)
        cmd = factory._build_llama_serve_command()

        # Check that -n parameter is not added for negative values
        assert "-n" not in cmd

    @patch('ramalama.daemon.service.command_factory.check_nvidia')
    @patch('ramalama.daemon.service.command_factory.check_metal')
    def test_llama_serve_command_max_tokens_with_runtime_args(self, mock_check_metal, mock_check_nvidia):
        """Test that max_tokens works alongside runtime_args."""
        mock_check_nvidia.return_value = False
        mock_check_metal.return_value = False

        request_args = {
            "max_tokens": 256,
            "ctx_size": 2048,
            "temp": "0.8",
            "ngl": -1,
            "threads": 4,
            "runtime_args": ["--custom-arg", "custom-value"],
            "debug": False,
            "webui": "",
            "thinking": False,
            "seed": "",
        }

        factory = CommandFactory(self.mock_model, "llama.cpp", 8080, "/tmp/log", request_args)
        cmd = factory._build_llama_serve_command()

        # Check that both max_tokens and runtime_args are present
        assert "-n" in cmd
        n_index = cmd.index("-n")
        assert cmd[n_index + 1] == "256"
        assert "--custom-arg" in cmd
        assert "custom-value" in cmd

    def test_mlx_serve_command_not_implemented(self):
        """Test that MLX serve command raises NotImplementedError."""
        request_args = {
            "max_tokens": 512,
            "ctx_size": 2048,
            "temp": "0.8",
            "ngl": -1,
            "threads": 4,
            "runtime_args": [],
            "debug": False,
            "webui": "",
            "thinking": False,
            "seed": "",
        }

        factory = CommandFactory(self.mock_model, "mlx", 8080, "/tmp/log", request_args)

        with pytest.raises(NotImplementedError, match="MLX serve command building is not implemented yet"):
            factory._build_mlx_serve_command()


class TestMaxTokensIntegration:
    """Integration tests for max_tokens functionality."""

    def test_max_tokens_end_to_end_config_to_command(self):
        """Test max_tokens flow from config through CLI to command generation."""
        # Simulate environment variable setting
        env = {"RAMALAMA_MAX_TOKENS": "1024"}

        with patch("ramalama.config.load_file_config", return_value={}):
            config = default_config(env)
            # Environment variables are loaded as strings
            assert config.max_tokens == "1024"

        # Simulate CLI argument parsing
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--max-tokens",
            dest="max_tokens",
            type=int,
            default=config.max_tokens,
            help="maximum number of tokens to generate (0 = unlimited)",
        )

        args = parser.parse_args(["--max-tokens", "512"])  # CLI overrides config
        assert args.max_tokens == 512

        # Simulate context creation
        ctx = RamalamaArgsContext.from_argparse(args)
        assert ctx.max_tokens == 512

        # Simulate command factory usage
        mock_model = Mock()
        mock_model._get_entry_model_path.return_value = "/test/model/path"
        mock_model._get_mmproj_path.return_value = None
        mock_model._get_chat_template_path.return_value = None
        mock_model.model_name = "test_model"

        request_args = {
            "max_tokens": ctx.max_tokens,
            "ctx_size": 2048,
            "temp": "0.8",
            "ngl": -1,
            "threads": 4,
            "runtime_args": [],
            "debug": False,
            "webui": "",
            "thinking": False,
            "seed": "",
        }

        factory = CommandFactory(mock_model, "llama.cpp", 8080, "/tmp/log", request_args)

        with patch('ramalama.daemon.service.command_factory.check_nvidia', return_value=False):
            with patch('ramalama.daemon.service.command_factory.check_metal', return_value=False):
                cmd = factory._build_llama_serve_command()

                # Verify the final command includes the max_tokens parameter
                assert "-n" in cmd
                n_index = cmd.index("-n")
                assert cmd[n_index + 1] == "512"

    def test_max_tokens_zero_unlimited_behavior(self):
        """Test that max_tokens=0 results in unlimited generation (no -n parameter)."""
        # Test with max_tokens = 0
        request_args = {
            "max_tokens": 0,
            "ctx_size": 2048,
            "temp": "0.8",
            "ngl": -1,
            "threads": 4,
            "runtime_args": [],
            "debug": False,
            "webui": "",
            "thinking": False,
            "seed": "",
        }

        mock_model = Mock()
        mock_model._get_entry_model_path.return_value = "/test/model/path"
        mock_model._get_mmproj_path.return_value = None
        mock_model._get_chat_template_path.return_value = None
        mock_model.model_name = "test_model"

        factory = CommandFactory(mock_model, "llama.cpp", 8080, "/tmp/log", request_args)

        with patch('ramalama.daemon.service.command_factory.check_nvidia', return_value=False):
            with patch('ramalama.daemon.service.command_factory.check_metal', return_value=False):
                cmd = factory._build_llama_serve_command()

                # Verify no -n parameter is added for unlimited generation
                assert "-n" not in cmd

    def test_max_tokens_validation_edge_cases(self):
        """Test max_tokens validation with edge cases."""
        # Test very large values
        env = {"RAMALAMA_MAX_TOKENS": "999999"}

        with patch("ramalama.config.load_file_config", return_value={}):
            config = default_config(env)
            # Environment variables are loaded as strings
            assert config.max_tokens == "999999"

        # Test zero value
        env = {"RAMALAMA_MAX_TOKENS": "0"}

        with patch("ramalama.config.load_file_config", return_value={}):
            config = default_config(env)
            # Environment variables are loaded as strings
            assert config.max_tokens == "0"

        # Test negative value
        env = {"RAMALAMA_MAX_TOKENS": "-1"}

        with patch("ramalama.config.load_file_config", return_value={}):
            config = default_config(env)
            # Environment variables are loaded as strings
            assert config.max_tokens == "-1"
