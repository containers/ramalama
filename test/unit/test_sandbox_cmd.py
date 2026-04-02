import json
from types import SimpleNamespace

import pytest

from ramalama.cli import parse_args_from_cmd
from ramalama.sandbox import Goose, OpenCode

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


def _make_opencode_args(engine="podman"):
    """Create minimal args for OpenCode tests."""
    return SimpleNamespace(
        engine=engine,
        dryrun=False,
        quiet=True,
        opencode_image="ghcr.io/anomalyco/opencode:latest",
        name="ramalama_model_abc",
        port="8080",
        thinking=False,
        workdir=None,
        subcommand="sandbox",
        ARGS=[],
    )


# --- Parametrized tests shared by both agents ---


@pytest.mark.parametrize("agent", ["goose", "opencode"])
def test_sandbox_model_positional(agent):
    """Sandbox cli should accept a model as a positional argument"""
    _, args = parse_args_from_cmd(["sandbox", agent, TEST_MODEL])
    assert args.MODEL == "hf://Qwen/Qwen3-4B-GGUF/Qwen3-4B-Q4_K_M.gguf"


@pytest.mark.parametrize("agent", ["goose", "opencode"])
def test_sandbox_requires_container_engine(agent):
    """Sandbox cli should raise when no container engine is configured"""
    _, args = parse_args_from_cmd(["sandbox", agent, TEST_MODEL])
    args.container = False
    with pytest.raises(ValueError, match="ramalama sandbox requires a container engine"):
        args.func(args)


@pytest.mark.parametrize("agent", ["goose", "opencode"])
def test_sandbox_subcommand(agent):
    """CLI should handle sandbox subcommand"""
    _, args = parse_args_from_cmd(["sandbox", agent, TEST_MODEL])
    assert args.subcommand == "sandbox"


@pytest.mark.parametrize("agent", ["goose", "opencode"])
def test_sandbox_agent_subcommand(agent):
    """CLI should set sandbox_agent correctly"""
    _, args = parse_args_from_cmd(["sandbox", agent, TEST_MODEL])
    assert args.subcommand == "sandbox"
    assert args.sandbox_agent == agent


@pytest.mark.parametrize("agent", ["goose", "opencode"])
def test_sandbox_thinking(agent):
    """Inference-specific options like 'thinking' should be handled"""
    _, args = parse_args_from_cmd(["sandbox", agent, "--thinking=off", TEST_MODEL])
    assert not args.thinking


@pytest.mark.parametrize("agent", ["goose", "opencode"])
def test_sandbox_workdir_default_none(agent):
    """Default workdir option should be None"""
    _, args = parse_args_from_cmd(["sandbox", agent, TEST_MODEL])
    assert args.workdir is None


@pytest.mark.parametrize("agent", ["goose", "opencode"])
def test_sandbox_workdir_option(agent):
    """CLI should parse -w/--workdir."""
    _, args = parse_args_from_cmd(["sandbox", agent, TEST_MODEL, "-w", "/tmp"])
    assert args.workdir == "/tmp"

    _, args = parse_args_from_cmd(["sandbox", agent, TEST_MODEL, "--workdir", "/tmp"])
    assert args.workdir == "/tmp"


def test_sandbox_no_subcommand(capsys):
    """Running 'ramalama sandbox' with no subcommand should print help"""
    _, args = parse_args_from_cmd(["sandbox"])
    # Calling the default func should print help (not raise)
    args.func(args)
    captured = capsys.readouterr()
    assert "goose" in captured.out
    assert "opencode" in captured.out


# --- Parametrized agent construction tests ---


@pytest.mark.parametrize("agent", ["goose", "opencode"])
def test_agent_network(agent):
    """Agent should setup container networking"""
    args = _make_args() if agent == "goose" else _make_opencode_args()
    obj = Goose(args, "test-model") if agent == "goose" else OpenCode(args, "test-model")
    assert "--network=container:ramalama_model_abc" in obj.engine.exec_args


@pytest.mark.parametrize("agent", ["goose", "opencode"])
def test_agent_interactive(agent):
    """Agent should set the -i option"""
    args = _make_args() if agent == "goose" else _make_opencode_args()
    obj = Goose(args, "test-model") if agent == "goose" else OpenCode(args, "test-model")
    assert "-i" in obj.engine.exec_args


@pytest.mark.parametrize("agent", ["goose", "opencode"])
def test_agent_workdir(agent):
    """Agent should add -v and --workdir=/work when workdir is set."""
    args = _make_args() if agent == "goose" else _make_opencode_args()
    args.workdir = "/tmp/myproject"
    obj = Goose(args, "test-model") if agent == "goose" else OpenCode(args, "test-model")
    cmd = obj.engine.exec_args
    assert "--workdir=/work" in cmd
    assert "/tmp/myproject:/work:rw" in cmd


@pytest.mark.parametrize("agent", ["goose", "opencode"])
def test_agent_no_workdir(agent):
    """Agent should not add volume or --workdir when workdir is not set."""
    args = _make_args() if agent == "goose" else _make_opencode_args()
    obj = Goose(args, "test-model") if agent == "goose" else OpenCode(args, "test-model")
    cmd = obj.engine.exec_args
    assert "--workdir=/work" not in cmd
    assert "-v" not in cmd


# --- Goose-specific tests ---


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


# --- OpenCode-specific tests ---


def test_opencode_default_image():
    """OpenCode subcommand should provide a default opencode image"""
    _, args = parse_args_from_cmd(["sandbox", "opencode", TEST_MODEL])
    assert args.opencode_image.startswith("ghcr.io/anomalyco/opencode:")


def test_opencode_custom_image():
    """OpenCode subcommand should handle the --opencode-image option"""
    _, args = parse_args_from_cmd(["sandbox", "opencode", TEST_MODEL, "--opencode-image", "myimage:v1"])
    assert args.opencode_image == "myimage:v1"


def test_opencode_env_vars():
    """OpenCode should set OPENCODE_CONFIG_CONTENT with proper JSON config"""
    args = _make_opencode_args()
    opencode = OpenCode(args, "Qwen3-4B-Q4_K_M")
    cmd = opencode.engine.exec_args
    assert "run" in cmd
    assert "--rm" in cmd
    # Find the OPENCODE_CONFIG_CONTENT env var
    config_arg = None
    for arg in cmd:
        if arg.startswith("OPENCODE_CONFIG_CONTENT="):
            config_arg = arg
            break
    assert config_arg is not None, "OPENCODE_CONFIG_CONTENT not found in command"
    config_json = config_arg.split("=", 1)[1]
    config = json.loads(config_json)
    assert config["provider"]["ramalama"]["npm"] == "@ai-sdk/openai-compatible"
    assert config["provider"]["ramalama"]["options"]["baseURL"] == "http://localhost:8080/v1"
    assert config["provider"]["ramalama"]["options"]["apiKey"] == "ramalama"
    assert "Qwen3-4B-Q4_K_M" in config["provider"]["ramalama"]["models"]


def test_opencode_with_tty(monkeypatch):
    """OpenCode should launch TUI (no extra args) when run with a tty"""
    monkeypatch.setattr("ramalama.engine.sys.stdin.isatty", lambda: True)
    args = _make_opencode_args()
    opencode = OpenCode(args, "test-model")
    # The last arg should be the image, no extra command
    assert opencode.engine.exec_args[-1] == args.opencode_image


def test_opencode_no_tty(monkeypatch):
    """OpenCode should run "run -" when run without a tty, to read commands from stdin"""
    monkeypatch.setattr("ramalama.engine.sys.stdin.isatty", lambda: False)
    args = _make_opencode_args()
    opencode = OpenCode(args, "test-model")
    assert opencode.engine.exec_args[-2:] == ["run", "-"]


def test_opencode_args():
    """OpenCode should run "run <message>" when args are passed on the command-line"""
    args = _make_opencode_args()
    args.ARGS = ["hello", "ramalama"]
    opencode = OpenCode(args, "test-model")
    assert opencode.engine.exec_args[-2:] == ["run", "hello ramalama"]
