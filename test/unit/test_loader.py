"""Unit tests for the plugin loader's assemble_command function."""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from ramalama.plugins.loader import assemble_command


def make_cli_args(**kwargs) -> argparse.Namespace:
    defaults = {
        "runtime": "llama.cpp",
        "subcommand": "serve",
        "container": True,
        "generate": None,
        "dryrun": False,
        "ngl": -1,
        "threads": 4,
        "temp": 0.8,
        "seed": None,
        "ctx_size": 0,
        "cache_reuse": None,
        "max_tokens": 0,
        "port": "8080",
        "host": "::",
        "logfile": None,
        "debug": False,
        "webui": "on",
        "thinking": True,
        "model_draft": None,
        "runtime_args": [],
        "gguf": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


@patch("ramalama.plugins.loader.get_runtime")
def test_assemble_command_dispatches_to_plugin(mock_get_runtime):
    mock_plugin = MagicMock()
    mock_plugin.handle_subcommand.return_value = ["llama-server", "--port", "8080"]
    mock_get_runtime.return_value = mock_plugin

    cli_args = make_cli_args(runtime="llama.cpp", subcommand="serve")
    result = assemble_command(cli_args)

    mock_get_runtime.assert_called_once_with("llama.cpp")
    mock_plugin.handle_subcommand.assert_called_once_with("serve", cli_args)
    assert result == ["llama-server", "--port", "8080"]


def test_assemble_command_raises_for_unknown_runtime():
    cli_args = make_cli_args(runtime="non-existing-runtime")
    with pytest.raises(ValueError, match="Unknown runtime: 'non-existing-runtime'"):
        assemble_command(cli_args)


@patch("ramalama.plugins.loader.get_runtime")
def test_assemble_command_raises_for_unsupported_command(mock_get_runtime):
    mock_plugin = MagicMock()
    mock_plugin.handle_subcommand.side_effect = NotImplementedError("plugin does not implement command 'execute'")
    mock_get_runtime.return_value = mock_plugin

    cli_args = make_cli_args(subcommand="execute")
    with pytest.raises(NotImplementedError, match="plugin does not implement command 'execute'"):
        assemble_command(cli_args)


@patch("ramalama.plugins.loader.get_runtime")
def test_assemble_command_passes_correct_runtime_and_subcommand(mock_get_runtime):
    mock_plugin = MagicMock()
    mock_plugin.handle_subcommand.return_value = []
    mock_get_runtime.return_value = mock_plugin

    cli_args = make_cli_args(runtime="vllm", subcommand="run")
    assemble_command(cli_args)

    mock_get_runtime.assert_called_once_with("vllm")
    mock_plugin.handle_subcommand.assert_called_once()
    assert mock_plugin.handle_subcommand.call_args[0][0] == "run"
