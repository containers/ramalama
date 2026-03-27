from types import SimpleNamespace

import pytest

from ramalama.cli import parse_args_from_cmd, sandbox_cli
from ramalama.sandbox import Goose

TEST_MODEL = "qwen3:4b"


def _make_args(engine="podman"):
    """Create minimal args for Goose tests."""
    return SimpleNamespace(
        engine=engine,
        dryrun=False,
        quiet=True,
        goose_image="ghcr.io/block/goose:latest",
        name="ramalama_model_abc",
        port="8080",
        thinking=False,
        workdir=None,
        subcommand="sandbox",
        ARGS=[],
    )


def test_sandbox_model_positional():
    """Sandbox cli should accept a model as a positional argument"""
    _, args = parse_args_from_cmd(["sandbox", "goose", TEST_MODEL])
    assert args.MODEL == "hf://Qwen/Qwen3-4B-GGUF/Qwen3-4B-Q4_K_M.gguf"


def test_sandbox_requires_container_engine():
    """Sandbox cli should raise when no container engine is configured"""
    _, args = parse_args_from_cmd(["sandbox", "goose", TEST_MODEL])
    args.container = False
    with pytest.raises(ValueError, match="ramalama sandbox requires a container engine"):
        sandbox_cli(args)


def test_sandbox_subcommand():
    """CLI should handle sandbox subcommand"""
    _, args = parse_args_from_cmd(["sandbox", "goose", TEST_MODEL])
    assert args.subcommand == "sandbox"


def test_sandbox_no_subcommand(capsys):
    """Running 'ramalama sandbox' with no subcommand should print help"""
    _, args = parse_args_from_cmd(["sandbox"])
    # Calling the default func should print help (not raise)
    args.func(args)
    captured = capsys.readouterr()
    assert "goose" in captured.out


def test_sandbox_thinking():
    """Inference-specific options like "thinking" should be handled"""
    _, args = parse_args_from_cmd(["sandbox", "goose", "--thinking=off", TEST_MODEL])
    assert not args.thinking


def test_sandbox_goose_subcommand():
    """CLI should set sandbox_agent to 'goose' and subcommand to 'sandbox'"""
    _, args = parse_args_from_cmd(["sandbox", "goose", TEST_MODEL])
    assert args.subcommand == "sandbox"
    assert args.sandbox_agent == "goose"


def test_goose_default_image():
    """Goose subcommand should provide a default goose image"""
    _, args = parse_args_from_cmd(["sandbox", "goose", TEST_MODEL])
    assert args.goose_image.startswith("ghcr.io/block/goose:")


def test_goose_custom_image():
    """Goose subcommand should handle the --goose-image option"""
    _, args = parse_args_from_cmd(["sandbox", "goose", TEST_MODEL, "--goose-image", "myimage:v1"])
    assert args.goose_image == "myimage:v1"


def test_goose_env_vars():
    """Goose should set various env vars"""
    args = _make_args()
    goose = Goose(args, "Qwen3-4B-Q4_K_M")
    cmd = goose.engine.exec_args
    assert cmd[0] == "podman"
    assert "run" in cmd
    assert "--rm" in cmd
    assert "GOOSE_PROVIDER=openai" in cmd
    assert "OPENAI_HOST=http://localhost:8080" in cmd
    assert "OPENAI_API_KEY=ramalama" in cmd
    assert "GOOSE_MODEL=Qwen3-4B-Q4_K_M" in cmd


def test_goose_network():
    """Goose should setup container networking"""
    args = _make_args()
    goose = Goose(args, "test-model")
    assert "--network=container:ramalama_model_abc" in goose.engine.exec_args


def test_goose_interactive():
    """Goose should set the -i option"""
    args = _make_args()
    goose = Goose(args, "test-model")
    assert "-i" in goose.engine.exec_args


def test_goose_with_tty(monkeypatch):
    """Goose should run the session command when run with a tty"""
    monkeypatch.setattr("ramalama.engine.sys.stdin.isatty", lambda: True)
    args = _make_args()
    goose = Goose(args, "test-model")
    assert goose.engine.exec_args[-1] == "session"


def test_goose_no_tty(monkeypatch):
    """Goose should run "run -i -" when run without a tty, to read commands from stdin"""
    monkeypatch.setattr("ramalama.engine.sys.stdin.isatty", lambda: False)
    args = _make_args()
    goose = Goose(args, "test-model")
    assert goose.engine.exec_args[-3:] == ["run", "-i", "-"]


def test_goose_args():
    """Goose should run "run -t" when args are passed on the command-line"""
    args = _make_args()
    args.ARGS = ["hello", "ramalama"]
    goose = Goose(args, "test-model")
    assert goose.engine.exec_args[-3:] == ["run", "-t", " ".join(args.ARGS)]


def test_sandbox_workdir_default_none():
    """Default workdir option should be None"""
    _, args = parse_args_from_cmd(["sandbox", "goose", TEST_MODEL])
    assert args.workdir is None


def test_sandbox_workdir_option():
    """CLI should parse -w/--workdir."""
    _, args = parse_args_from_cmd(["sandbox", "goose", TEST_MODEL, "-w", "/tmp"])
    assert args.workdir == "/tmp"

    _, args = parse_args_from_cmd(["sandbox", "goose", TEST_MODEL, "--workdir", "/tmp"])
    assert args.workdir == "/tmp"


def test_goose_workdir():
    """Goose should add -v and --workdir=/work when workdir is set."""
    args = _make_args()
    args.workdir = "/tmp/myproject"
    goose = Goose(args, "test-model")
    cmd = goose.engine.exec_args
    assert "--workdir=/work" in cmd
    assert "/tmp/myproject:/work:rw" in cmd


def test_goose_no_workdir():
    """Goose should not add volume or --workdir when workdir is not set."""
    args = _make_args()
    goose = Goose(args, "test-model")
    cmd = goose.engine.exec_args
    assert "--workdir=/work" not in cmd
    assert "-v" not in cmd
