import re
from pathlib import Path
from subprocess import STDOUT, CalledProcessError
from test.conftest import skip_if_no_container
from test.e2e.utils import RamalamaExecWorkspace, check_output, get_ramalama_subcommands

import pytest

DEFAULT_IMAGE_PATTERN = re.compile(
    r"--image IMAGE\s+OCI container image to run with the specified AI model "
    r"\(default: (?P<image>.+):(?P<image_tag>[\d\w.]+)\)",
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


@pytest.mark.e2e
def test_help_command_flags():
    # Test for regression of #7273 (spurious "--remote" help on output)
    for help_opt in ["help", "-h", "--help"]:
        result = check_output(["ramalama", help_opt])
        assert re.search(r"^usage: ramalama \[-h] \[--container] \[--debug] \[--dryrun] \[--engine ENGINE]", result)


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

    # FIXME: some check_help tests are missing


@pytest.mark.e2e
def test_default_image():
    result = check_output(["ramalama", "--help"])
    match = DEFAULT_IMAGE_PATTERN.search(result)
    assert match and match.group("image") == "quay.io/ramalama/ramalama"


@pytest.mark.e2e
def test_default_image_by_env_variable():
    result = check_output(["ramalama", "--help"], env={"RAMALAMA_IMAGE": "quay.io/ramalama-dev/ramalama:latest"})
    match = DEFAULT_IMAGE_PATTERN.search(result)
    assert match
    assert match.group("image") == "quay.io/ramalama-dev/ramalama"
    assert match.group("image_tag") == "latest"


@pytest.mark.e2e
def test_default_image_by_config():
    config = """
    [ramalama]
    image="quay.io/ramalama-dev/ramalama:latest"
    """

    with RamalamaExecWorkspace(config=config) as ctx:
        result = ctx.check_output(["ramalama", "--help"])
        match = DEFAULT_IMAGE_PATTERN.search(result)
        assert match
        assert match.group("image") == "quay.io/ramalama-dev/ramalama"
        assert match.group("image_tag") == "latest"


@pytest.mark.e2e
def test_default_image_by_env_variable_and_config():
    config = """
    [ramalama]
    image="quay.io/ramalama-dev/ramalama:latest"
    """
    env_vars = {"RAMALAMA_IMAGE": "quay.io/ramalama-by-env-var/ramalama:latest"}

    with RamalamaExecWorkspace(config=config, env_vars=env_vars) as ctx:
        result = ctx.check_output(["ramalama", "--help"])
        match = DEFAULT_IMAGE_PATTERN.search(result)
        assert match
        assert match.group("image") == "quay.io/ramalama-by-env-var/ramalama"
        assert match.group("image_tag") == "latest"


@pytest.mark.e2e
def test_default_container_engine():
    result = check_output(["ramalama", "--help"])
    match = DEFAULT_CONTAINER_ENGINE_PATTERN.search(result)
    assert match and match.group("engine") in ['podman', 'docker']


@pytest.mark.e2e
def test_default_container_engine_by_env_variable():
    result = check_output(["ramalama", "--help"], env={"RAMALAMA_CONTAINER_ENGINE": "podman-test"})
    match = DEFAULT_CONTAINER_ENGINE_PATTERN.search(result)
    assert match and match.group("engine") == "podman-test"


@pytest.mark.e2e
def test_default_container_engine_by_config():
    engine_name = "podman-test"
    config = """
    [ramalama]
    engine="{}"
    """.format(
        engine_name
    )

    with RamalamaExecWorkspace(config=config, container_engine_discover=False) as ctx:
        result = ctx.check_output(["ramalama", "--help"])
        match = DEFAULT_CONTAINER_ENGINE_PATTERN.search(result)
        assert match and match.group("engine") == engine_name


@pytest.mark.e2e
def test_default_container_engine_variable_precedence():
    env_engine_name = "env-engine"
    config_engine_name = "config-engine"
    # param_engine_name = "param-engine"

    config = f"""
    [ramalama]
    engine="{config_engine_name}"
    """
    env_vars = {"RAMALAMA_CONTAINER_ENGINE": env_engine_name}

    with RamalamaExecWorkspace(config=config, env_vars=env_vars) as ctx:
        # RAMALAMA_CONTAINER_ENGINE > RAMALAMA_CONFIG
        result = ctx.check_output(["ramalama", "--help"])
        match = DEFAULT_CONTAINER_ENGINE_PATTERN.search(result)
        assert match and match.group("engine") == env_engine_name

        # # FIXME: That is not true
        # # --engine > RAMALAMA_CONTAINER_ENGINE > RAMALAMA_CONFIG
        # result = ctx.check_output(["ramalama", "--engine", param_engine_name, "--help"])
        # match = DEFAULT_CONTAINER_ENGINE_PATTERN.search(result)
        # assert match and match.group("engine") == param_engine_name


@pytest.mark.e2e
def test_default_runtime():
    result = check_output(["ramalama", "--help"])
    match = DEFAULT_RUNTIME_PATTERN.search(result)
    assert match and match.group("runtime") == "llama.cpp"


@pytest.mark.e2e
def test_default_runtime_by_config():
    config = """
    [ramalama]
    runtime="vllm"
    """
    with RamalamaExecWorkspace(config=config) as ctx:
        result = ctx.check_output(["ramalama", "--help"])
        match = DEFAULT_RUNTIME_PATTERN.search(result)
        assert match and match.group("runtime") == "vllm"


@pytest.mark.e2e
def test_default_store():
    result = check_output(["ramalama", "--help"])
    match = DEFAULT_STORE_PATTERN.search(result)
    assert match and match.group("store_path") == (Path.home() / ".local" / "share" / "ramalama").as_posix()


@pytest.mark.e2e
def test_default_store_variable_precedence():
    config = """
    [ramalama]
    store="{workspace_dir}/.local/share/ramalama"
    """

    with RamalamaExecWorkspace(config=config) as ctx:
        # RAMALAMA_CONFIG > default
        result = ctx.check_output(["ramalama", "--help"])
        match = DEFAULT_STORE_PATTERN.search(result)
        assert match and match.group("store_path") == f"{ctx.workspace_dir}/.local/share/ramalama"

        # FIXME: Test is not working
        # # --store > RAMALAMA_CONFIG > default
        # result = ctx.check_output(["ramalama", "--store", f"{ctx.workspace_dir}/.ramalama", "--help"])
        # match = DEFAULT_STORE_PATTERN.search(result)
        # assert match and match.group("store_path") == f"{ctx.workspace_dir}/.ramalama"


@pytest.mark.e2e
@skip_if_no_container
def test_default_container():
    result = check_output(["ramalama", "--help"])
    match = DEFAULT_CONTAINER_PATTERN.search(result)
    assert match and match.group("value") == "True"


@pytest.mark.e2e
@skip_if_no_container
def test_default_container_by_env_variable():
    result = check_output(["ramalama", "--help"], env={"RAMALAMA_IN_CONTAINER": "False"})
    match = DEFAULT_CONTAINER_PATTERN.search(result)
    assert match and match.group("value") == "False"


@pytest.mark.e2e
@skip_if_no_container
def test_default_container_by_config():
    config = """
    [ramalama]
    container=false
    """

    with RamalamaExecWorkspace(config=config, container_discover=False) as ctx:
        result = ctx.check_output(["ramalama", "--help"])
        match = DEFAULT_CONTAINER_PATTERN.search(result)
        assert match and match.group("value") == "False"


@pytest.mark.e2e
def test_unsupported_transport_message():
    with pytest.raises(CalledProcessError) as exc_info:
        check_output(["ramalama", "pull", "foobar"], env={"RAMALAMA_TRANSPORT": "test-transport"}, stderr=STDOUT)

    assert exc_info.value.returncode == 1
    assert re.search(
        r"Error: transport \"{}\" not supported.".format("test-transport"),
        exc_info.value.output.decode("utf-8"),
    )


@pytest.mark.e2e
def test_default_port():
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
