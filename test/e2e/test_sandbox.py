import re
import subprocess

import pytest

from test.conftest import skip_if_no_container, skip_if_not_windows, skip_if_ppc64le, skip_if_s390x, skip_if_windows
from test.e2e.utils import RamalamaExecWorkspace, check_output

TEST_MODEL = "qwen3:1.7b"


def _dryrun_cmd(agent):
    return ["ramalama", "-q", "--dryrun", "sandbox", agent, TEST_MODEL]


RAMALAMA_SANDBOX_DRY_RUN = _dryrun_cmd("goose")


@pytest.fixture(scope="module")
def sandbox_ctx():
    config = """
    [ramalama]
    store="{workspace_dir}/.local/share/ramalama"
    """
    with RamalamaExecWorkspace(config=config) as ctx:
        ctx.check_call(["ramalama", "-q", "pull", TEST_MODEL])
        yield ctx


# --- Parametrized dryrun tests ---


@pytest.mark.e2e
@skip_if_no_container
@skip_if_windows
@pytest.mark.parametrize("agent", ["goose", "opencode"])
def test_sandbox_dryrun_default(agent):
    """Dryrun should print container commands including run."""
    result = check_output(_dryrun_cmd(agent), stdin=subprocess.DEVNULL)
    if agent == "goose":
        assert re.search(r"run -i -", result)
    else:
        assert re.search(r"run -", result)


@pytest.mark.e2e
@skip_if_no_container
@skip_if_not_windows
def test_sandbox_dryrun_default_windows():
    """Dryrun on Windows should print container commands including session"""
    # Apparently sys.stdin.isatty() always returns True on Windows
    result = check_output(RAMALAMA_SANDBOX_DRY_RUN)
    assert re.search(r"session", result)


@pytest.mark.e2e
@skip_if_no_container
@pytest.mark.parametrize("agent", ["goose", "opencode"])
def test_sandbox_dryrun_network(agent):
    """Dryrun output should include container networking."""
    result = check_output(_dryrun_cmd(agent))
    assert re.search(r"--network=container:", result)


@pytest.mark.e2e
@skip_if_no_container
@pytest.mark.parametrize("agent", ["goose", "opencode"])
def test_sandbox_dryrun_custom_model(agent):
    """Custom model should appear in the model server dryrun output."""
    result = check_output(_dryrun_cmd(agent)[:-1] + ["gpt-oss"])
    assert "gpt-oss" in result


@pytest.mark.e2e
@skip_if_no_container
@pytest.mark.parametrize("agent", ["goose", "opencode"])
def test_sandbox_dryrun_custom_workdir(agent):
    """--workdir should mount the directory and set --workdir=/work."""
    result = check_output(_dryrun_cmd(agent) + ["-w", "/tmp"])
    assert "/tmp:/work:rw" in result
    assert "--workdir=/work" in result


# --- Goose-specific dryrun tests ---


@pytest.mark.e2e
@skip_if_no_container
def test_sandbox_dryrun_goose_env_vars():
    """Dryrun output should include Goose environment variables."""
    result = check_output(RAMALAMA_SANDBOX_DRY_RUN)
    assert "GOOSE_PROVIDER=openai" in result
    assert "OPENAI_API_KEY=ramalama" in result
    assert re.search(r"OPENAI_HOST=http://localhost:\d+", result)


@pytest.mark.e2e
@skip_if_no_container
def test_sandbox_dryrun_goose_thinking():
    """Dryrun output should include env var enabling thinking output."""
    result = check_output(RAMALAMA_SANDBOX_DRY_RUN)
    assert "GOOSE_CLI_SHOW_THINKING=true" in result


@pytest.mark.e2e
@skip_if_no_container
def test_sandbox_dryrun_goose_custom_image():
    """Custom --goose-image should appear in the goose container command."""
    result = check_output(RAMALAMA_SANDBOX_DRY_RUN + ["--goose-image", "mygoose:v2"])
    assert "mygoose:v2" in result


# --- OpenCode-specific dryrun tests ---


@pytest.mark.e2e
@skip_if_no_container
def test_sandbox_dryrun_opencode_env_vars():
    """Dryrun output should include OpenCode config env var."""
    result = check_output(_dryrun_cmd("opencode"))
    assert "OPENCODE_CONFIG_CONTENT=" in result
    assert "@ai-sdk/openai-compatible" in result

    # Validate that the generated OpenCode config wires baseURL and model correctly.
    # We keep this regex-based so it remains robust to minor JSON formatting changes.
    # Base URL must point at the local ramalama sandbox server
    assert re.search(
        r'baseURL"\s*:\s*"http://localhost:\d{4}/v1"',
        result,
    ), "Expected OpenCode config to include baseURL http://localhost:<port>/v1"

    # Model alias must resolve to our ramalama model; keep this flexible but specific
    assert re.search(
        r'"models"\s*:\s*{"[a-zA-Z0-9._/-]+"',
        result,
    ), "Expected OpenCode config to include models section"


@pytest.mark.e2e
@skip_if_no_container
def test_sandbox_dryrun_opencode_custom_image():
    """Custom --opencode-image should appear in the opencode container command."""
    result = check_output(_dryrun_cmd("opencode") + ["--opencode-image", "myopencode:v2"])
    assert "myopencode:v2" in result


# --- Live run tests ---


@pytest.mark.e2e
@skip_if_no_container
@skip_if_ppc64le
@skip_if_s390x
@pytest.mark.parametrize("agent", ["goose", "opencode"])
def test_sandbox_run(sandbox_ctx, agent):
    """Agent should run successfully."""
    result = sandbox_ctx.check_output(["ramalama", "sandbox", agent, "--thinking=off", TEST_MODEL, "hi"])
    assert result


@pytest.mark.e2e
@skip_if_no_container
@skip_if_ppc64le
@skip_if_s390x
@pytest.mark.parametrize("agent", ["goose", "opencode"])
def test_sandbox_run_cmdline(sandbox_ctx, tmp_path, container_engine, agent):
    """Agent should successfully execute instructions provided on the command-line."""
    # Not sure how to grant container user 1000 permissions to write to the
    # local user's directory under docker
    if container_engine == "docker":
        tmp_path.chmod(0o777)
    # fmt: off
    result = sandbox_ctx.check_output(
        [
            "ramalama", "sandbox", agent, "-w", tmp_path, "--seed=1", "--temp=0", TEST_MODEL,
            "Please", "create", "a", "pyproject.toml", "for", "a", "project", "called",
            "ramalama", "and", "write", "it", "to", "the", "current", "directory.",
            "Ensure", "it", "contains", "a", "project", "section.",
        ]
    )
    pyproject = tmp_path / "pyproject.toml"
    assert pyproject.exists(), f"missing pyproject.toml, agent output: {result}"
    content = pyproject.read_text()
    assert "[project]" in content, f"no [project] in pyproject.toml, agent output: {result}"
    assert "ramalama" in content, f"no ramalama in pyproject.toml, agent output: {result}"


@pytest.mark.e2e
@skip_if_no_container
@skip_if_ppc64le
@skip_if_s390x
@skip_if_windows
@pytest.mark.parametrize("agent", ["goose", "opencode"])
def test_sandbox_run_stdin(sandbox_ctx, tmp_path, agent):
    """Agent should successfully execute instructions provided on stdin"""
    fpath = tmp_path / "stdin.txt"
    fpath.write_text("What is the atomic number of molybdenum?")
    result = sandbox_ctx.check_output(
        ["ramalama", "sandbox", agent, "--thinking=off", "--seed=1", "--temp=0", TEST_MODEL], stdin=fpath.open()
    )
    assert "42" in result
