import json
import os
from types import SimpleNamespace

import pytest

from ramalama.cli import parse_args_from_cmd
from ramalama.sandbox import Agent, Goose, OpenClaw, OpenCode

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


def _make_openclaw_args(engine="podman"):
    """Create minimal args for OpenClaw tests."""
    return SimpleNamespace(
        engine=engine,
        dryrun=False,
        quiet=True,
        openclaw_image="ghcr.io/openclaw/openclaw:latest",
        openclaw_port=18789,
        state_dir=None,
        name="ramalama_model_abc",
        port="8080",
        thinking=False,
        workdir=None,
        subcommand="sandbox",
        debug=False,
        ARGS=[],
    )


def _build_agent(agent: str, model: str = "test-model"):
    args = _make_args() if agent == "goose" else _make_opencode_args() if agent == "opencode" else _make_openclaw_args()
    cls = Goose if agent == "goose" else OpenCode if agent == "opencode" else OpenClaw
    return args, cls(args, model)


# --- Parametrized tests shared by both agents ---


@pytest.mark.parametrize("agent", ["goose", "opencode", "openclaw"])
def test_sandbox_model_positional(agent):
    """Sandbox cli should accept a model as a positional argument"""
    _, args = parse_args_from_cmd(["sandbox", agent, TEST_MODEL])
    assert args.MODEL == "hf://Qwen/Qwen3-4B-GGUF/Qwen3-4B-Q4_K_M.gguf"


@pytest.mark.parametrize("agent", ["goose", "opencode", "openclaw"])
def test_sandbox_requires_container_engine(agent):
    """Sandbox cli should raise when no container engine is configured"""
    _, args = parse_args_from_cmd(["sandbox", agent, TEST_MODEL])
    args.container = False
    with pytest.raises(ValueError, match="ramalama sandbox requires a container engine"):
        args.func(args)


@pytest.mark.parametrize("agent", ["goose", "opencode", "openclaw"])
def test_sandbox_subcommand(agent):
    """CLI should handle sandbox subcommand"""
    _, args = parse_args_from_cmd(["sandbox", agent, TEST_MODEL])
    assert args.subcommand == "sandbox"


@pytest.mark.parametrize("agent", ["goose", "opencode", "openclaw"])
def test_sandbox_agent_subcommand(agent):
    """CLI should set sandbox_agent correctly"""
    _, args = parse_args_from_cmd(["sandbox", agent, TEST_MODEL])
    assert args.subcommand == "sandbox"
    assert args.sandbox_agent == agent


@pytest.mark.parametrize("agent", ["goose", "opencode", "openclaw"])
def test_sandbox_thinking(agent):
    """Inference-specific options like 'thinking' should be handled"""
    _, args = parse_args_from_cmd(["sandbox", agent, "--thinking=off", TEST_MODEL])
    assert not args.thinking


@pytest.mark.parametrize("agent", ["goose", "opencode", "openclaw"])
def test_sandbox_workdir_default_none(agent):
    """Default workdir option should be None"""
    _, args = parse_args_from_cmd(["sandbox", agent, TEST_MODEL])
    assert args.workdir is None


@pytest.mark.parametrize("agent", ["goose", "opencode", "openclaw"])
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
    assert "openclaw" in captured.out


# --- Parametrized agent construction tests ---


@pytest.mark.parametrize("agent", ["goose", "opencode", "openclaw"])
def test_agent_network(agent):
    """Agent should setup container networking"""
    _, obj = _build_agent(agent)
    try:
        assert "--network=container:ramalama_model_abc" in obj.engine.exec_args
    finally:
        getattr(obj, "cleanup", lambda: None)()


@pytest.mark.parametrize("agent", ["goose", "opencode", "openclaw"])
def test_agent_interactive(agent):
    """Agent should set the -i option"""
    _, obj = _build_agent(agent)
    try:
        assert "-i" in obj.engine.exec_args
    finally:
        getattr(obj, "cleanup", lambda: None)()


@pytest.mark.parametrize("agent", ["goose", "opencode", "openclaw"])
def test_agent_workdir(agent):
    """Agent should add -v and --workdir=/work when workdir is set."""
    args = _make_args() if agent == "goose" else _make_opencode_args() if agent == "opencode" else _make_openclaw_args()
    cls = Goose if agent == "goose" else OpenCode if agent == "opencode" else OpenClaw
    args.workdir = "/tmp/myproject"
    obj = cls(args, "test-model")
    try:
        cmd = obj.engine.exec_args
        assert "--workdir=/work" in cmd
        assert "/tmp/myproject:/work:rw" in cmd
    finally:
        getattr(obj, "cleanup", lambda: None)()


@pytest.mark.parametrize("agent", ["goose", "opencode", "openclaw"])
def test_agent_no_workdir(agent):
    """Agent should not add volume or --workdir when workdir is not set."""
    _, obj = _build_agent(agent)
    try:
        cmd = obj.engine.exec_args
        assert "--workdir=/work" not in cmd
        # Check no workdir volume is mounted (OpenClaw mounts a config volume, which is fine)
        workdir_volumes = [arg for arg in cmd if ":/work:" in arg]
        assert len(workdir_volumes) == 0
    finally:
        getattr(obj, "cleanup", lambda: None)()


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
    assert config["model"] == "ramalama/Qwen3-4B-Q4_K_M"
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
    assert opencode.engine.exec_args[-2:] == ["run", "--thinking=true"]


def test_opencode_args():
    """OpenCode should run "run <message>" when args are passed on the command-line"""
    args = _make_opencode_args()
    args.ARGS = ["hello", "ramalama"]
    opencode = OpenCode(args, "test-model")
    assert opencode.engine.exec_args[-4:] == ["run", "--thinking=true", "hello", "ramalama"]


# --- OpenClaw-specific tests ---


def test_openclaw_default_image():
    """OpenClaw subcommand should provide a default OpenClaw image"""
    _, args = parse_args_from_cmd(["sandbox", "openclaw", TEST_MODEL])
    assert args.openclaw_image.startswith("ghcr.io/openclaw/openclaw:")


def test_openclaw_custom_image():
    """OpenClaw subcommand should handle the --openclaw-image option"""
    _, args = parse_args_from_cmd(["sandbox", "openclaw", TEST_MODEL, "--openclaw-image", "myimage:v1"])
    assert args.openclaw_image == "myimage:v1"


def test_openclaw_env_vars():
    """OpenClaw should set environment for local OpenAI-compatible provider on both engines"""
    args = _make_openclaw_args()
    openclaw = OpenClaw(args, "Qwen3-4B-Q4_K_M")
    try:
        # Client engine env vars
        cmd = openclaw.engine.exec_args
        assert "OPENAI_BASE_URL=http://localhost:8080/v1" in cmd
        assert "OPENAI_API_KEY=ramalama" in cmd
        assert "OPENCLAW_CONFIG_PATH=/etc/openclaw/ramalama.json" in cmd
        assert "OPENCLAW_SKIP_CHANNELS=1" in cmd
        assert "OPENCLAW_SKIP_GMAIL_WATCHER=1" in cmd
        assert "OPENCLAW_SKIP_CRON=1" in cmd
        assert "OPENCLAW_SKIP_CANVAS_HOST=1" in cmd
        # Gateway engine env vars
        gw_cmd = openclaw.gateway_engine.exec_args
        assert "OPENAI_BASE_URL=http://localhost:8080/v1" in gw_cmd
        assert "OPENAI_API_KEY=ramalama" in gw_cmd
        assert "OPENCLAW_CONFIG_PATH=/etc/openclaw/ramalama.json" in gw_cmd
    finally:
        openclaw.cleanup()


def test_openclaw_env_custom_port():
    """OpenClaw should honour a non-default port in env and launch config"""
    args = _make_openclaw_args()
    args.port = "9999"
    openclaw = OpenClaw(args, "Qwen3-4B-Q4_K_M")
    try:
        cmd = openclaw.engine.exec_args
        assert "OPENAI_BASE_URL=http://localhost:9999/v1" in cmd
        # Config file should also use the overridden port
        with open(openclaw.config_file_path) as f:
            config = json.load(f)
        assert config["models"]["providers"]["openai"]["baseUrl"] == "http://localhost:9999/v1"
    finally:
        openclaw.cleanup()


def test_openclaw_config_file():
    """OpenClaw should write a correct JSON config file"""
    args = _make_openclaw_args()
    model_name = "test-model"
    openclaw = OpenClaw(args, model_name)
    try:
        assert os.path.exists(openclaw.config_file_path)
        with open(openclaw.config_file_path) as f:
            config = json.load(f)
        # Validate provider configuration
        assert config["models"]["providers"]["openai"]["api"] == "openai-completions"
        assert config["models"]["providers"]["openai"]["apiKey"] == "ramalama"
        assert "8080" in config["models"]["providers"]["openai"]["baseUrl"]
        # Validate default agent model
        assert config["agents"]["defaults"]["model"]["primary"] == f"openai/{model_name}"
        # Validate gateway configuration
        assert config["gateway"]["mode"] == "local"
        assert config["gateway"]["bind"] == "loopback"
        assert config["gateway"]["port"] == 18789
    finally:
        openclaw.cleanup()


def test_openclaw_config_workspace_when_workdir_set():
    """OpenClaw should set agents.defaults.workspace when workdir is provided."""
    args = _make_openclaw_args()
    args.workdir = "/tmp/myproject"
    openclaw = OpenClaw(args, "test-model")
    try:
        with open(openclaw.config_file_path) as f:
            config = json.load(f)
        assert config["agents"]["defaults"]["workspace"] == "/work"
    finally:
        openclaw.cleanup()


def test_openclaw_cleanup():
    """OpenClaw cleanup should remove the temporary config file"""
    args = _make_openclaw_args()
    openclaw = OpenClaw(args, "test-model")
    config_path = openclaw.config_file_path
    assert os.path.exists(config_path)
    openclaw.cleanup()
    assert not os.path.exists(config_path)
    # cleanup should be idempotent
    openclaw.cleanup()


def test_openclaw_with_tty(monkeypatch):
    """OpenClaw client should launch TUI connecting to gateway when run with a tty"""
    monkeypatch.setattr("ramalama.engine.sys.stdin.isatty", lambda: True)
    args = _make_openclaw_args()
    openclaw = OpenClaw(args, "test-model")
    try:
        assert openclaw.engine.exec_args[-4:] == ["openclaw", "tui", "--session", "main"]
    finally:
        openclaw.cleanup()


def test_openclaw_no_tty(monkeypatch):
    """OpenClaw client should read stdin as message when run without a tty"""
    monkeypatch.setattr("ramalama.engine.sys.stdin.isatty", lambda: False)
    args = _make_openclaw_args()
    openclaw = OpenClaw(args, "test-model")
    try:
        assert openclaw.engine.exec_args[-2:] == [
            "-c",
            'msg="$(cat)"; exec openclaw agent --session-id ramalama --message "$msg"',
        ]
    finally:
        openclaw.cleanup()


def test_openclaw_args():
    """OpenClaw client should run a one-shot agent call connecting to gateway"""
    args = _make_openclaw_args()
    args.ARGS = ["hello", "ramalama"]
    openclaw = OpenClaw(args, "test-model")
    try:
        assert openclaw.engine.exec_args[-6:] == [
            "openclaw",
            "agent",
            "--session-id",
            "ramalama",
            "--message",
            "hello ramalama",
        ]
    finally:
        openclaw.cleanup()


def test_openclaw_gateway_engine():
    """OpenClaw should create a detached gateway engine running openclaw gateway run"""
    args = _make_openclaw_args()
    openclaw = OpenClaw(args, "test-model")
    try:
        gw = openclaw.gateway_engine.exec_args
        # Gateway should be detached
        assert "-d" in gw
        # Gateway should NOT be interactive
        assert "-i" not in gw
        # Gateway should share network with model server
        assert "--network=container:ramalama_model_abc" in gw
        # Gateway command should be openclaw gateway run
        assert gw[-3:] == ["openclaw", "gateway", "run"]
    finally:
        openclaw.cleanup()


def test_openclaw_gateway_config_mounted():
    """Both gateway and client engines should mount the same config file"""
    args = _make_openclaw_args()
    openclaw = OpenClaw(args, "test-model")
    try:
        config_path = openclaw.config_file_path
        # Both should contain a volume mount for the config file
        gw_volumes = [a for a in openclaw.gateway_engine.exec_args if config_path in a]
        client_volumes = [a for a in openclaw.engine.exec_args if config_path in a]
        assert len(gw_volumes) > 0, "Gateway should mount the config file"
        assert len(client_volumes) > 0, "Client should mount the config file"
        # Both should mount to the same container path
        assert "/etc/openclaw/ramalama.json" in gw_volumes[0]
        assert "/etc/openclaw/ramalama.json" in client_volumes[0]
    finally:
        openclaw.cleanup()


def test_openclaw_debug_log_level():
    """OpenClaw should set OPENCLAW_LOG_LEVEL=debug on both engines when debug is True"""
    args = _make_openclaw_args()
    args.debug = True
    openclaw = OpenClaw(args, "test-model")
    try:
        assert "OPENCLAW_LOG_LEVEL=debug" in openclaw.engine.exec_args
        assert "OPENCLAW_LOG_LEVEL=debug" in openclaw.gateway_engine.exec_args
    finally:
        openclaw.cleanup()


def test_openclaw_debug_verbose_in_agent_args():
    """OpenClaw should pass --verbose to agent command when debug is True."""
    args = _make_openclaw_args()
    args.debug = True
    args.ARGS = ["hello"]
    openclaw = OpenClaw(args, "test-model")
    try:
        cmd = openclaw.engine.exec_args
        assert "openclaw" in cmd
        assert "agent" in cmd
        assert "--verbose" in cmd
    finally:
        openclaw.cleanup()


def test_openclaw_debug_verbose_in_stdin_path(monkeypatch):
    """OpenClaw should include --verbose in stdin agent command when debug is True."""
    monkeypatch.setattr("ramalama.engine.sys.stdin.isatty", lambda: False)
    args = _make_openclaw_args()
    args.debug = True
    openclaw = OpenClaw(args, "test-model")
    try:
        assert openclaw.engine.exec_args[-2:] == [
            "-c",
            'msg="$(cat)"; exec openclaw agent --verbose --session-id ramalama --message "$msg"',
        ]
    finally:
        openclaw.cleanup()


def test_openclaw_run_handles_start_wait_and_cleanup(monkeypatch):
    """OpenClaw.run should start gateway, wait for readiness, run client, and cleanup in finally."""
    calls = []

    def _record_run_cmd(cmd, stdout=None, stdin=None):
        calls.append(cmd)

    monkeypatch.setattr("ramalama.sandbox.run_cmd", _record_run_cmd)
    monkeypatch.setattr(
        "ramalama.sandbox.stop_container", lambda args, name, remove=False: calls.append(["stop", name])
    )
    monkeypatch.setattr(OpenClaw, "_wait_for_gateway_ready", lambda self, timeout=30: calls.append(["wait"]))

    args = _make_openclaw_args()
    args.ARGS = ["hello"]
    openclaw = OpenClaw(args, "test-model")
    config_path = openclaw.config_file_path
    openclaw.run()

    assert calls[0] == openclaw.gateway_engine.exec_args
    assert calls[1] == ["wait"]
    assert calls[2] == openclaw.engine.exec_args
    assert calls[3] == ["stop", openclaw._gateway_name]
    assert not os.path.exists(config_path)


def test_openclaw_run_cleans_up_on_failure(monkeypatch):
    """OpenClaw.run should cleanup even if client launch fails."""
    cleaned = {"value": False}

    monkeypatch.setattr(OpenClaw, "start_gateway", lambda self: None)
    monkeypatch.setattr(OpenClaw, "_wait_for_gateway_ready", lambda self, timeout=30: None)
    monkeypatch.setattr(Agent, "run", lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(OpenClaw, "cleanup", lambda self: cleaned.__setitem__("value", True))

    args = _make_openclaw_args()
    openclaw = OpenClaw(args, "test-model")
    with pytest.raises(RuntimeError, match="boom"):
        openclaw.run()
    assert cleaned["value"]


def test_openclaw_no_debug_log_level():
    """OpenClaw should not set OPENCLAW_LOG_LEVEL when debug is False"""
    args = _make_openclaw_args()
    args.debug = False
    openclaw = OpenClaw(args, "test-model")
    try:
        assert "OPENCLAW_LOG_LEVEL=debug" not in openclaw.engine.exec_args
        assert "OPENCLAW_LOG_LEVEL=debug" not in openclaw.gateway_engine.exec_args
    finally:
        openclaw.cleanup()


def test_openclaw_state_dir():
    """OpenClaw should mount state-dir on gateway engine"""
    args = _make_openclaw_args()
    args.state_dir = "/tmp/openclaw-state"
    openclaw = OpenClaw(args, "test-model")
    try:
        gw = openclaw.gateway_engine.exec_args
        assert "OPENCLAW_STATE_DIR=/var/lib/openclaw" in gw
        volume_args = [arg for arg in gw if "/tmp/openclaw-state:" in arg]
        assert len(volume_args) > 0, "Expected a volume mount for state_dir on gateway"
        assert "/var/lib/openclaw:rw" in volume_args[0]
    finally:
        openclaw.cleanup()
