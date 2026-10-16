"""CLI setup must avoid hardware probes for commands that do not use a runtime."""

from unittest.mock import patch

import pytest

from ramalama.cli import get_parser, parse_args_from_cmd
from ramalama.config import ActiveConfig
from ramalama.plugins.loader import get_runtime


@pytest.fixture(autouse=True)
def runtime(monkeypatch):
    monkeypatch.setattr(ActiveConfig(), "runtime", "llama.cpp")
    monkeypatch.setattr(ActiveConfig(), "store", ActiveConfig().store)


@pytest.mark.parametrize(
    "command",
    [
        "chat",
        "containers",
        "ps",
        "info",
        "inspect",
        "list",
        "ls",
        "login",
        "logout",
        "models",
        "pull",
        "push",
        "rm",
        "stop",
        "version",
    ],
)
def test_builtin_help_does_not_probe_gpu(command, capsys):
    with patch("ramalama.common.get_accel", side_effect=AssertionError("unexpected GPU probe")):
        with pytest.raises(SystemExit) as exc:
            parse_args_from_cmd([command, "--help"])
    assert exc.value.code == 0
    canonical = {"ps": "containers", "ls": "list"}.get(command, command)
    assert f"ramalama {canonical}" in capsys.readouterr().out


@pytest.mark.parametrize("cmd", [["list"], ["models"], ["--store", "serve", "ls"]])
def test_builtin_parsing_does_not_register_runtime(cmd):
    with patch.object(get_runtime("llama.cpp"), "register_subcommands", side_effect=AssertionError("runtime setup")):
        _, args = parse_args_from_cmd(cmd)
    assert args.subcommand == cmd[-1]


@pytest.mark.parametrize("cmd", [["--help"], ["--help", "list"], ["-h", "models"]])
def test_global_help_includes_runtime_commands(cmd, capsys):
    with pytest.raises(SystemExit) as exc:
        parse_args_from_cmd(cmd)
    assert exc.value.code == 0
    output = capsys.readouterr().out
    for command in ["run", "serve", "sandbox", "daemon"]:
        assert command in output


@pytest.mark.parametrize(
    "command",
    [None, "help", "run", "serve", "bench", "benchmark", "perplexity", "convert", "benchmarks", "sandbox", "daemon"],
)
def test_full_parser_retains_commands(command):
    parser = get_parser(subcommand=command)
    for name in ["run", "serve", "sandbox", "daemon"]:
        assert name in parser.format_help()


def test_custom_runtime_command_is_registered():
    def register(subparsers):
        subparsers.add_parser("custom-runtime-command")

    with patch.object(get_runtime("llama.cpp"), "register_subcommands", side_effect=register):
        _, args = parse_args_from_cmd(["custom-runtime-command"])
    assert args.subcommand == "custom-runtime-command"
