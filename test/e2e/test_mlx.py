import re
import subprocess
from subprocess import CalledProcessError

import pytest

from test.conftest import skip_if_apple_silicon, skip_if_no_mlx, skip_if_not_apple_silicon
from test.e2e.utils import RamalamaExecWorkspace, check_output

MODEL = "hf://mlx-community/SmolLM-135M-4bit"


@pytest.mark.e2e
def test_runtime_mlx_help_shows_mlx_option():
    """ramalama --runtime=mlx help shows MLX option"""
    result = check_output(["ramalama", "--help"])
    assert "mlx" in result, "MLX should be listed as a runtime option"


@pytest.mark.e2e
@skip_if_not_apple_silicon
@skip_if_no_mlx
def test_runtime_mlx_automatically_enables_nocontainer():
    """MLX runtime should automatically set --nocontainer"""
    with RamalamaExecWorkspace() as ctx:
        result = ctx.check_output(["ramalama", "--runtime=mlx", "--dryrun", "run", MODEL])
        assert "podman" not in result and "docker" not in result, "should not use container runtime"


@pytest.mark.e2e
@skip_if_not_apple_silicon
@skip_if_no_mlx
def test_runtime_mlx_container_shows_warning_but_works():
    """When --container is explicitly used with MLX, it should warn but auto-switch to --nocontainer"""
    with RamalamaExecWorkspace() as ctx:
        result = ctx.check_output(["ramalama", "--runtime=mlx", "--container", "--dryrun", "run", MODEL])
        assert "podman" not in result and "docker" not in result, (
            "should not use container runtime even with --container flag"
        )


@pytest.mark.e2e
@skip_if_not_apple_silicon
@skip_if_no_mlx
def test_runtime_mlx_dryrun_run_shows_server_client_model():
    """ramalama --runtime=mlx --dryrun run should show the MLX server command with port specification"""
    with RamalamaExecWorkspace() as ctx:
        result = ctx.check_output(["ramalama", "--runtime=mlx", "--dryrun", "run", MODEL])
        assert re.search(r"mlx_lm\.server", result), "should use MLX server command"
        assert re.search(r"--port", result), "should include port specification"


@pytest.mark.e2e
@skip_if_not_apple_silicon
@skip_if_no_mlx
def test_runtime_mlx_dryrun_run_with_prompt_shows_server_client_model():
    """ramalama --runtime=mlx --dryrun run with a prompt should show the MLX server command with port specification"""
    with RamalamaExecWorkspace() as ctx:
        prompt = "Hello, how are you?"
        result = ctx.check_output(["ramalama", "--runtime=mlx", "--dryrun", "run", MODEL, prompt])
        assert re.search(r"mlx_lm\.server", result), "should use MLX server command"
        assert re.search(r"--port", result), "should include port specification"


@pytest.mark.e2e
@skip_if_not_apple_silicon
@skip_if_no_mlx
def test_runtime_mlx_dryrun_run_with_temperature():
    """ramalama --runtime=mlx --dryrun run with temperature should include temperature setting"""
    with RamalamaExecWorkspace() as ctx:
        result = ctx.check_output(["ramalama", "--runtime=mlx", "--dryrun", "run", "--temp", "0.5", MODEL, "test"])
        assert re.search(r"--temp\s+0\.5", result), "should include temperature setting"


@pytest.mark.e2e
@skip_if_not_apple_silicon
@skip_if_no_mlx
def test_runtime_mlx_dryrun_run_with_max_tokens():
    """ramalama --runtime=mlx --dryrun run with ctx-size should include max-tokens setting"""
    with RamalamaExecWorkspace() as ctx:
        result = ctx.check_output(["ramalama", "--runtime=mlx", "--dryrun", "run", "--ctx-size", "1024", MODEL, "test"])
        assert re.search(r"--max-tokens\s+1024", result), "should include max tokens setting"


@pytest.mark.e2e
@skip_if_not_apple_silicon
@skip_if_no_mlx
def test_runtime_mlx_dryrun_serve_shows_mlx_server_command():
    """ramalama --runtime=mlx --dryrun serve should show the MLX server command with a default-range port"""
    with RamalamaExecWorkspace() as ctx:
        result = ctx.check_output(["ramalama", "--runtime=mlx", "--dryrun", "serve", MODEL])
        assert re.search(r"mlx_lm\.server", result), "should use MLX server command"
        assert re.search(r"--port\s+80[89]\d", result), "should include default-range port"


@pytest.mark.e2e
@skip_if_not_apple_silicon
@skip_if_no_mlx
def test_runtime_mlx_dryrun_serve_with_custom_port():
    """ramalama --runtime=mlx --dryrun serve with a custom port should include the custom port"""
    with RamalamaExecWorkspace() as ctx:
        result = ctx.check_output(["ramalama", "--runtime=mlx", "--dryrun", "serve", "--port", "9090", MODEL])
        assert re.search(r"--port\s+9090", result), "should include custom port"


@pytest.mark.e2e
@skip_if_not_apple_silicon
@skip_if_no_mlx
def test_runtime_mlx_dryrun_serve_with_host():
    """ramalama --runtime=mlx --dryrun serve with a custom host should include the custom host"""
    with RamalamaExecWorkspace() as ctx:
        result = ctx.check_output(["ramalama", "--runtime=mlx", "--dryrun", "serve", "--host", "127.0.0.1", MODEL])
        assert re.search(r"--host\s+127\.0\.0\.1", result), "should include custom host"


@pytest.mark.e2e
@skip_if_apple_silicon
def test_runtime_mlx_run_fails_on_non_apple_silicon():
    """ramalama --runtime=mlx run should fail on non-Apple Silicon systems"""
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(["ramalama", "--runtime=mlx", "run", MODEL], stderr=subprocess.STDOUT)
        assert exc_info.value.returncode == 22
        assert re.search(r"MLX.*Apple Silicon", exc_info.value.output.decode("utf-8")), (
            "should show Apple Silicon requirement error"
        )


@pytest.mark.e2e
@skip_if_apple_silicon
def test_runtime_mlx_serve_fails_on_non_apple_silicon():
    """ramalama --runtime=mlx serve should fail on non-Apple Silicon systems"""
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(["ramalama", "--runtime=mlx", "serve", MODEL], stderr=subprocess.STDOUT)
        assert exc_info.value.returncode == 22
        assert re.search(r"MLX.*Apple Silicon", exc_info.value.output.decode("utf-8")), (
            "should show Apple Silicon requirement error"
        )


@pytest.mark.e2e
@skip_if_not_apple_silicon
@skip_if_no_mlx
def test_runtime_mlx_works_with_ollama_model_format():
    """ramalama --runtime=mlx should work with ollama model format"""
    with RamalamaExecWorkspace() as ctx:
        ollama_model = "ollama://smollm:135m"
        result = ctx.check_output(["ramalama", "--runtime=mlx", "--dryrun", "run", ollama_model])
        assert re.search(r"mlx_lm\.server", result), "should use MLX server command"


@pytest.mark.e2e
@skip_if_not_apple_silicon
@skip_if_no_mlx
def test_runtime_mlx_works_with_huggingface_model_format():
    """ramalama --runtime=mlx should work with huggingface model format"""
    with RamalamaExecWorkspace() as ctx:
        hf_model = "huggingface://microsoft/DialoGPT-small"
        result = ctx.check_output(["ramalama", "--runtime=mlx", "--dryrun", "run", hf_model])
        assert re.search(r"mlx_lm\.server", result), "should use MLX server command"


@pytest.mark.e2e
@skip_if_not_apple_silicon
@skip_if_no_mlx
def test_runtime_mlx_rejects_name_option():
    """ramalama --runtime=mlx should reject --name option"""
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(["ramalama", "--runtime=mlx", "run", "--name", "test", MODEL], stderr=subprocess.STDOUT)
        assert exc_info.value.returncode == 22
        assert re.search(r"--nocontainer.*--name.*conflict", exc_info.value.output.decode("utf-8")), (
            "should show conflict error"
        )


@pytest.mark.e2e
@skip_if_not_apple_silicon
@skip_if_no_mlx
def test_runtime_mlx_rejects_privileged_option():
    """ramalama --runtime=mlx should reject --privileged option"""
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(["ramalama", "--runtime=mlx", "run", "--privileged", MODEL], stderr=subprocess.STDOUT)
        assert exc_info.value.returncode == 22
        assert re.search(r"--nocontainer.*--privileged.*conflict", exc_info.value.output.decode("utf-8")), (
            "should show conflict error"
        )
