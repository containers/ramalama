import json
import os
import platform
import re
import string
from pathlib import Path
from subprocess import STDOUT, CalledProcessError

import pytest

from ramalama.version import version as ramalama_version
from test.conftest import skip_if_no_container
from test.e2e.utils import RamalamaExecWorkspace, check_output, get_ramalama_subcommands

DEFAULT_IMAGE_PATTERN = re.compile(
    r"--image IMAGE\s+(?P<help_msg>[\w\s]+)\s\(default:\s+(?P<image>[^:]+):(?P<image_tag>[^)]+)",
    re.MULTILINE,
)

DEFAULT_CONTAINER_PATTERN = re.compile(
    r"\s+The RAMALAMA_IN_CONTAINER environment variable modifies default behaviour. \(default: (?P<value>\w+)\)",
    re.MULTILINE,
)

DEFAULT_CONTAINER_ENGINE_PATTERN = re.compile(
    r"The RAMALAMA_CONTAINER_ENGINE environment variable modifies default behaviour. \(default: (?P<engine>[\w-]+)\)",
    re.MULTILINE,
)

DEFAULT_RUNTIME_PATTERN = re.compile(
    r"\s+specify the runtime to use; valid options are.*\s+\(default: (?P<runtime>[\w.]+)\)",
    re.MULTILINE,
)

DEFAULT_STORE_PATTERN = re.compile(
    r"\s+store AI Models in the specified directory \(default: (?P<store_path>.+)\)",
    re.MULTILINE,
)

DEFAULT_API_KEY_PATTERN = re.compile(
    r"--api-key API_KEY\s+.*\(default: (?P<api_key>.+)\)",
    re.MULTILINE,
)


@pytest.fixture()
def default_storage_path():
    # Check if running as root (Unix only)
    if hasattr(os, 'geteuid') and os.geteuid() == 0:
        return "/var/lib/ramalama"

    return str(Path("~/.local/share/ramalama").expanduser())


@pytest.mark.e2e
def test_help_command_flags():
    # Test for regression of #7273 (spurious "--remote" help on output)
    for help_opt in ["help", "-h", "--help"]:
        result = check_output(["ramalama", help_opt])
        assert re.search(r"^usage: ramalama \[-h] \[--debug.*] \[--dryrun] \[--engine {podman,docker}]", result)


@pytest.mark.e2e
@pytest.mark.parametrize(
    "subcommand",
    get_ramalama_subcommands(),
    ids=[f"ramalama {subcommand}" for subcommand in get_ramalama_subcommands()],
)
def test_help_output(subcommand):
    result = check_output(["ramalama", subcommand, "--help"])
    if subcommand == "benchmark":
        usage_cmd_name = "bench"
    elif subcommand == "ps":
        usage_cmd_name = "containers"
    elif subcommand == "ls":
        usage_cmd_name = "list"
    else:
        usage_cmd_name = subcommand

    # Check if usage exists in the help output
    assert result.startswith(f"usage: ramalama {usage_cmd_name}")

    # Check if the option section is rendered
    assert re.search("^options:$", result, re.MULTILINE)


@pytest.mark.e2e
@pytest.mark.parametrize("command", ["run", "bench", "serve"], ids=lambda x: f"ramalama {x}")
def test_default_image(monkeypatch, command):
    monkeypatch.delenv("RAMALAMA_DEFAULT_IMAGE", raising=False)
    monkeypatch.delenv("RAMALAMA_IMAGES", raising=False)
    result = check_output(["ramalama", command, "--help"])
    match = DEFAULT_IMAGE_PATTERN.search(result.replace("\n", ""))

    assert match
    help_msg = match.group("help_msg")
    assert " ".join(help_msg.split()) == "OCI container image to run with the specified AI model"
    image = match.group("image").strip()
    assert image.startswith("quay.io/ramalama/")
    image_tag = match.group("image_tag").strip()
    assert image_tag == "latest" or ramalama_version().startswith(image_tag)


@pytest.mark.e2e
@pytest.mark.parametrize("command", ["run", "bench", "serve"], ids=lambda x: f"ramalama {x}")
def test_default_image_by_env_variable(command):
    result = check_output(
        ["ramalama", command, "--help"], env={"RAMALAMA_IMAGE": "quay.io/ramalama-dev/ramalama:latest"}
    )
    match = DEFAULT_IMAGE_PATTERN.search(result.replace("\n", ""))
    remove_whitespaces = str.maketrans("", "", string.whitespace)

    assert match.group("image").translate(remove_whitespaces) == "quay.io/ramalama-dev/ramalama"
    assert match.group("image_tag").translate(remove_whitespaces) == "latest"


@pytest.mark.e2e
@pytest.mark.parametrize("command", ["run", "bench", "serve"], ids=lambda x: f"ramalama {x}")
def test_default_image_by_config(command):
    config = """
    [ramalama]
    image="quay.io/ramalama-dev/ramalama:latest"
    """

    with RamalamaExecWorkspace(config=config) as ctx:
        result = ctx.check_output(["ramalama", command, "--help"])
        match = DEFAULT_IMAGE_PATTERN.search(result.replace("\n", ""))
        remove_whitespaces = str.maketrans("", "", string.whitespace)

        assert match.group("image").translate(remove_whitespaces) == "quay.io/ramalama-dev/ramalama"
        assert match.group("image_tag").translate(remove_whitespaces) == "latest"


@pytest.mark.e2e
@pytest.mark.parametrize("command", ["run", "bench", "serve"], ids=lambda x: f"ramalama {x}")
def test_default_image_by_env_variable_and_config(command):
    config = """
    [ramalama]
    image="quay.io/ramalama-dev/ramalama:latest"
    """
    env_vars = {"RAMALAMA_IMAGE": "quay.io/ramalama-by-env-var/ramalama:latest"}

    with RamalamaExecWorkspace(config=config, env_vars=env_vars) as ctx:
        result = ctx.check_output(["ramalama", command, "--help"])
        match = DEFAULT_IMAGE_PATTERN.search(result.replace("\n", ""))
        remove_whitespaces = str.maketrans("", "", string.whitespace)

        assert match.group("image").translate(remove_whitespaces) == "quay.io/ramalama-by-env-var/ramalama"
        assert match.group("image_tag").translate(remove_whitespaces) == "latest"


@pytest.mark.e2e
def test_default_container_engine():
    result = check_output(["ramalama", "--help"])
    match = DEFAULT_CONTAINER_ENGINE_PATTERN.search(result.replace("\n", ""))
    assert match.group("engine") in ['podman', 'docker']


@pytest.mark.e2e
def test_default_container_engine_by_env_variable():
    result = check_output(["ramalama", "--help"], env={"RAMALAMA_CONTAINER_ENGINE": "podman-test"})
    match = DEFAULT_CONTAINER_ENGINE_PATTERN.search(result.replace("\n", ""))
    assert match and match.group("engine") == "podman-test"


@pytest.mark.e2e
def test_default_container_engine_by_config(monkeypatch):
    monkeypatch.delenv("RAMALAMA_CONTAINER_ENGINE", raising=False)
    engine_name = "podman-test"
    config = f"""
    [ramalama]
    engine="{engine_name}"
    """

    with RamalamaExecWorkspace(config=config, container_engine_discover=False) as ctx:
        result = ctx.check_output(["ramalama", "--help"])
        match = DEFAULT_CONTAINER_ENGINE_PATTERN.search(result.replace("\n", ""))
        assert match and match.group("engine") == engine_name


@pytest.mark.e2e
def test_default_container_engine_variable_precedence():
    env_engine_name = "env-engine"
    config_engine_name = "config-engine"
    param_engine_name = "docker"

    config = f"""
    [ramalama]
    engine="{config_engine_name}"
    """
    env_vars = {"RAMALAMA_CONTAINER_ENGINE": env_engine_name}

    with RamalamaExecWorkspace(config=config, env_vars=env_vars) as ctx:
        # CLI > RAMALAMA_CONTAINER_ENGINE > RAMALAMA_CONFIG
        result = ctx.check_output(["ramalama", "--help"])
        match = DEFAULT_CONTAINER_ENGINE_PATTERN.search(result.replace("\n", ""))
        assert match and match.group("engine") == env_engine_name

        result = ctx.check_output(["ramalama", "--engine", param_engine_name, "--help"])
        match = DEFAULT_CONTAINER_ENGINE_PATTERN.search(result.replace("\n", ""))
        assert match and match.group("engine") == "docker"


@pytest.mark.e2e
def test_container_engine_flag_validation():
    with pytest.raises(CalledProcessError) as exc_info:
        check_output(["ramalama", "--engine", "unsupported-engine", "--help"], stderr=STDOUT)

    assert exc_info.value.returncode == 2
    assert re.search(
        r".*ramalama: error: argument --engine: invalid choice: 'unsupported-engine' \(choose from .*\)",
        exc_info.value.output.decode("utf-8"),
    )


@pytest.mark.e2e
def test_default_runtime():
    result = check_output(["ramalama", "--help"])
    match = DEFAULT_RUNTIME_PATTERN.search(result.replace("\n", ""))
    assert match and match.group("runtime") == "llama.cpp"


@pytest.mark.e2e
def test_default_runtime_variable_precedence():
    env_runtime = "mlx"
    config_runtime = "lamma.cpp"
    param_runtime = "vllm"

    config = f"""
    [ramalama]
    runtime="{config_runtime}"
    """
    env_vars = {"RAMALAMA_RUNTIME": env_runtime}

    with RamalamaExecWorkspace(config=config, env_vars=env_vars) as ctx:
        # CLI > RAMALAMA_RUNTIME > RAMALAMA_CONFIG
        result = ctx.check_output(["ramalama", "--help"])
        match = DEFAULT_RUNTIME_PATTERN.search(result.replace("\n", ""))
        assert match and match.group("runtime") == env_runtime

        result = ctx.check_output(["ramalama", "--runtime", param_runtime, "--help"])
        match = DEFAULT_RUNTIME_PATTERN.search(result.replace("\n", ""))
        assert match and match.group("runtime") == param_runtime


@pytest.mark.e2e
def test_default_runtime_by_config():
    config = """
    [ramalama]
    runtime="mlx"
    """
    with RamalamaExecWorkspace(config=config) as ctx:
        result = ctx.check_output(["ramalama", "--help"])
        match = DEFAULT_RUNTIME_PATTERN.search(result.replace("\n", ""))
        assert match and match.group("runtime") == "mlx"


@pytest.mark.e2e
def test_default_store(default_storage_path):
    result = check_output(["ramalama", "--help"])
    match = DEFAULT_STORE_PATTERN.search(result.replace("\n", ""))

    assert match and match.group("store_path") == default_storage_path


@pytest.mark.e2e
def test_default_store_variable_precedence():
    config = """
    [ramalama]
    store="{workspace_dir}/.local/share/ramalama"
    """

    with RamalamaExecWorkspace(config=config) as ctx:
        # precedence: RAMALAMA_CONFIG > default
        result = ctx.check_output(["ramalama", "--help"])
        match = DEFAULT_STORE_PATTERN.search(result.replace("\n", ""))
        assert match and match.group("store_path") == str(
            Path(f"{ctx.workspace_dir}") / ".local" / "share" / "ramalama"
        )

        # precedence: --store > RAMALAMA_CONFIG > default
        result = ctx.check_output(["ramalama", "--store", f"{ctx.workspace_dir}/.ramalama", "--help"])
        match = DEFAULT_STORE_PATTERN.search(result.replace("\n", ""))
        assert match and match.group("store_path") == str(Path(f"{ctx.workspace_dir}") / ".ramalama")

        if platform.system() != "Darwin":
            result = ctx.check_output(["ramalama", "--store", f"{ctx.workspace_dir}/.ramalama", "info"])
            assert json.loads(result)["Store"] == str(Path(ctx.workspace_dir) / ".ramalama")


@pytest.mark.e2e
@skip_if_no_container
def test_default_container():
    with RamalamaExecWorkspace(container_discover=False) as ctx:
        result = ctx.check_output(["ramalama", "--help"])
        match = DEFAULT_CONTAINER_PATTERN.search(result.replace("\n", ""))
        assert match and match.group("value") == "False"


@pytest.mark.e2e
@skip_if_no_container
def test_default_container_by_env_variable():
    with RamalamaExecWorkspace(container_discover=False) as ctx:
        result = ctx.check_output(["ramalama", "--help"], env={"RAMALAMA_IN_CONTAINER": "false"})
        match = DEFAULT_CONTAINER_PATTERN.search(result.replace("\n", ""))
        assert match and match.group("value") == "True"


@pytest.mark.e2e
@skip_if_no_container
def test_default_container_by_config():
    config = """
    [ramalama]
    container=false
    """

    with RamalamaExecWorkspace(config=config, container_discover=False) as ctx:
        result = ctx.check_output(["ramalama", "--help"])
        match = DEFAULT_CONTAINER_PATTERN.search(result.replace("\n", ""))
        assert match and match.group("value") == "True"


@pytest.mark.e2e
def test_unsupported_transport_message():
    test_transport = "test-transport"
    with pytest.raises(CalledProcessError) as exc_info:
        check_output(["ramalama", "pull", "foobar"], env={"RAMALAMA_TRANSPORT": test_transport}, stderr=STDOUT)

    assert exc_info.value.returncode == 22
    assert re.search(
        f"Error: transport \"{test_transport}\" not supported. Must be oci, huggingface, modelscope, or ollama.",
        exc_info.value.output.decode("utf-8"),
    )


@pytest.mark.e2e
def test_default_port():
    with RamalamaExecWorkspace() as ctx:
        result = ctx.check_output(["ramalama", "serve", "--help"])
        assert re.search(".*port for AI Model server to listen on.*8080", result)


@pytest.mark.e2e
def test_default_port_by_config():
    config = """
    [ramalama]
    port="1776"
    """

    with RamalamaExecWorkspace(config=config) as ctx:
        result = ctx.check_output(["ramalama", "serve", "--help"])
        assert re.search(".*port for AI Model server to listen on.*1776", result)


@pytest.mark.e2e
def test_help_rm_message_without_arguments():
    with pytest.raises(CalledProcessError) as exc_info:
        check_output(["ramalama", "rm"], stderr=STDOUT)

    assert exc_info.value.returncode == 22
    assert re.search(
        r"Error: one MODEL or --all must be specified",
        exc_info.value.output.decode("utf-8"),
    )


@pytest.mark.e2e
def test_default_api_key():
    import random
    import string

    # Generate a random API key similar to bats safename function
    api_key = f"e_t1-{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}"

    # Test 1: With RAMALAMA_API_KEY environment variable, it should show as default
    result = check_output(
        ["ramalama", "chat", "--help"],
        env={"RAMALAMA_API_KEY": api_key, "RAMALAMA_CONFIG": "NUL" if platform.system() == "Windows" else '/dev/null'},
    )
    match = f"default: {api_key}" in result
    assert match, f"API key from environment should show as (default: {api_key})"

    # Test 2: Environment variable takes precedence over config file
    config_api_key = f"config_key_{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}"
    config = f"""
    [ramalama]
    api_key = "{config_api_key}"
    """

    with RamalamaExecWorkspace(config=config, env_vars={"RAMALAMA_API_KEY": api_key}) as ctx:
        result = ctx.check_output(["ramalama", "chat", "--help"])
        match = f"default: {api_key}" in result
        assert match, (
            f"Environment variable should override config file: expected \
        {api_key}"
        )
