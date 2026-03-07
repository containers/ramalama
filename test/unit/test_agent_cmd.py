from types import SimpleNamespace

from ramalama.agent import GooseEngine
from ramalama.cli import parse_args_from_cmd


def _make_args(engine="podman"):
    """Create minimal args for GooseEngine tests."""
    return SimpleNamespace(
        engine=engine,
        dryrun=False,
        quiet=True,
        agent_image="ghcr.io/block/goose:latest",
        name="ramalama_model_abc",
        port="8080",
        thinking=False,
        workdir=None,
        ARGS=[],
    )


def test_agent_default_model():
    """Agent cli should provide a default model"""
    _, args = parse_args_from_cmd(["agent"])
    assert args.model == "hf://Qwen/Qwen3-1.7B-GGUF/Qwen3-1.7B-Q8_0.gguf"


def test_agent_custom_model():
    """Agent cli should handle the --model option"""
    model = "hf://ggml-org/gemma-3-4b-it-GGUF"
    _, args = parse_args_from_cmd(["agent", "--model", model])
    assert args.model == model


def test_agent_default_agent_image():
    """Agent cli should provide a default agent image"""
    _, args = parse_args_from_cmd(["agent"])
    assert args.agent_image.startswith("ghcr.io/block/goose:")


def test_agent_custom_agent_image():
    """Agent cli should handle the --agent-image option"""
    _, args = parse_args_from_cmd(["agent", "--agent-image", "myimage:v1"])
    assert args.agent_image == "myimage:v1"


def test_agent_subcommand():
    """CLI should handle agent subcommand"""
    _, args = parse_args_from_cmd(["agent"])
    assert args.subcommand == "agent"


def test_goose_engine_env_vars():
    """GooseEngine should set various env vars"""
    args = _make_args()
    goose = GooseEngine(
        args,
        model_name="Qwen3-1.7B-Q8_0",
    )
    cmd = goose.exec_args
    assert cmd[0] == "podman"
    assert "run" in cmd
    assert "--rm" in cmd
    assert "GOOSE_PROVIDER=openai" in cmd
    assert "OPENAI_HOST=http://localhost:8080" in cmd
    assert "OPENAI_API_KEY=ramalama" in cmd
    assert "GOOSE_MODEL=Qwen3-1.7B-Q8_0" in cmd


def test_goose_engine_network():
    """GooseEngine should setup container networking"""
    args = _make_args()
    goose = GooseEngine(
        args,
        model_name="test-model",
    )
    assert "--network=container:ramalama_model_abc" in goose.exec_args


def test_goose_engine_interactive():
    """GooseEngine should set the -i option"""
    args = _make_args()
    goose = GooseEngine(
        args,
        model_name="test-model",
    )
    assert "-i" in goose.exec_args


def test_goose_engine_with_tty(monkeypatch):
    """GooseEngine should run the session command when run with a tty"""
    monkeypatch.setattr("ramalama.engine.sys.stdin.isatty", lambda: True)
    args = _make_args()
    goose = GooseEngine(
        args,
        model_name="test-model",
    )
    assert goose.exec_args[-1] == "session"


def test_goose_engine_no_tty(monkeypatch):
    """GooseEngine should run "run -i -" when run without a tty, to read commands from stdin"""
    monkeypatch.setattr("ramalama.engine.sys.stdin.isatty", lambda: False)
    args = _make_args()
    goose = GooseEngine(
        args,
        model_name="test-model",
    )
    assert goose.exec_args[-3:] == ["run", "-i", "-"]


def test_goose_engine_args():
    """GooseEngine should run "run -t" when args are passed on the command-line"""
    args = _make_args()
    args.ARGS = ["hello", "ramalama"]
    goose = GooseEngine(
        args,
        model_name="test-model",
    )
    assert goose.exec_args[-3:] == ["run", "-t", " ".join(args.ARGS)]


def test_agent_workdir_default_none():
    """Default workdir option should be None"""
    _, args = parse_args_from_cmd(["agent"])
    assert args.workdir is None


def test_agent_workdir_option():
    """CLI should parse -w/--workdir."""
    _, args = parse_args_from_cmd(["agent", "-w", "/tmp"])
    assert args.workdir == "/tmp"

    _, args = parse_args_from_cmd(["agent", "--workdir", "/tmp"])
    assert args.workdir == "/tmp"


def test_goose_engine_workdir():
    """GooseEngine should add -v and --workdir=/work when workdir is set."""
    args = _make_args()
    args.workdir = "/tmp/myproject"
    goose = GooseEngine(
        args,
        model_name="test-model",
    )
    cmd = goose.exec_args
    assert "--workdir=/work" in cmd
    assert "/tmp/myproject:/work:rw" in cmd


def test_goose_engine_no_workdir():
    """GooseEngine should not add volume or --workdir when workdir is not set."""
    args = _make_args()
    goose = GooseEngine(
        args,
        model_name="test-model",
    )
    cmd = goose.exec_args
    assert "--workdir=/work" not in cmd
    assert "-v" not in cmd
