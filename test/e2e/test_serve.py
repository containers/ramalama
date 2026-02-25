import itertools
import json
import logging
import os
import platform
import random
import re
import string
import time
from contextlib import contextmanager
from pathlib import Path
from subprocess import STDOUT, CalledProcessError

import pytest
import yaml

from test.conftest import (
    skip_if_container,
    skip_if_darwin,
    skip_if_docker,
    skip_if_gh_actions_darwin,
    skip_if_no_container,
    skip_if_ppc64le,
    skip_if_s390x,
)
from test.e2e.utils import RamalamaExecWorkspace, check_output, get_full_model_name


@contextmanager
def chdir(path):
    old_dir = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_dir)


DRY_RUN_TEST_MODEL = "dry_run_model"
RAMALAMA_DRY_RUN = ["ramalama", "-q", "--dryrun", "serve"]


@pytest.fixture(scope="module")
def shared_ctx(test_model):
    config = """
    [ramalama]
    store="{workspace_dir}/.local/share/ramalama"
    """
    with RamalamaExecWorkspace(config=config) as ctx:
        ctx.check_call(["ramalama", "-q", "pull", test_model])
        yield ctx


@pytest.mark.e2e
@skip_if_no_container
def test_basic_dry_run():
    ramalama_info = json.loads(check_output(["ramalama", "info"]))
    conman = ramalama_info["Engine"]["Name"]

    result = check_output(RAMALAMA_DRY_RUN + [DRY_RUN_TEST_MODEL])
    assert result.startswith(f"{conman} run --rm")
    assert not re.search(r".*-t -i", result), "run without terminal"


# fmt: off
@pytest.mark.e2e
@pytest.mark.parametrize(
    "extra_params, pattern, config, env_vars, expected",
    [
        pytest.param(
            [], f".*{DRY_RUN_TEST_MODEL}.*", None, None, True,
            id="check model name", marks=skip_if_no_container
        ),
        pytest.param(
            [], r".*--name ramalama-.", None, None, True,
            id="check default --name flag", marks=skip_if_no_container
        ),
        pytest.param(
            [], r".*--cache-reuse 256", None, None, True,
            id="check --cache-reuse default value (256)", marks=skip_if_no_container
        ),
        pytest.param(
            [], r".*--no-webui", None, None, False,
            id="check --no-webui is not present by default", marks=skip_if_no_container
        ),
        pytest.param(
            ["--webui", "off"], r".*--no-webui", None, None, True,
            id="check --no-webui", marks=skip_if_no_container
        ),
        pytest.param(
            ["--name", "foobar"], r".*--name foobar .*", None, None, True,
            id="check --name foobar", marks=skip_if_no_container
        ),
        pytest.param(
            ["--name", "foobar"], r".*--network", None, None, False,
            id="check --network is not present when run within container", marks=skip_if_no_container
        ),
        pytest.param(
            ["--name", "foobar"], r".*--host 0.0.0.0", None, None, True,
            id="check --host is not present when run within container", marks=skip_if_no_container
        ),
        pytest.param(
            ["--name", "foobar"], f".*{DRY_RUN_TEST_MODEL}.*", None, None, True,
            id="check test_model with --name foobar", marks=skip_if_no_container
        ),
        pytest.param(
            ["--name", "foobar"], r".*--seed", None, None, False,
            id="check --seed is not present by default", marks=skip_if_no_container
        ),
        pytest.param(
            ["--network", "bridge", "--host", "127.1.2.3", "--name", "foobar"],
            r".*--network bridge", None, None, True,
            id="check --network", marks=skip_if_no_container
        ),
        pytest.param(
            ["--host", "127.1.2.3"],
            r".*--host 127.1.2.3", None, None, False,
            id="check --host is not modified when run within container", marks=skip_if_no_container
        ),
        pytest.param(
            ["--host", "127.1.2.3", "--port", "1234"],
            r".*-p 127.1.2.3:1234:1234", None, None, True,
            id="check -p is modified when run within container", marks=skip_if_no_container
        ),
        pytest.param(
            [], r".*--temp 0.8", None, None, True,
            id="check --temp default value", marks=skip_if_no_container
        ),
        pytest.param(
            ["--temp", "0.1"], r".*--temp 0.1", None, None, True,
            id="check --temp", marks=skip_if_no_container
        ),
        pytest.param(
            ["--seed", "1234", "--name", "foobar"], r".*--seed 1234",
            None, {"RAMALAMA_CONFIG": "NUL" if platform.system() == "Windows" else '/dev/null'}, True,
            id="check --seed 1234 with RAMALAMA_CONFIG=/dev/null", marks=skip_if_no_container,
        ),
        pytest.param(
            ["--name", "foobar"], r".*--pull newer", None, {
                "RAMALAMA_CONFIG": "NUL" if platform.system() == "Windows" else '/dev/null'
            }, True,
            id="check pull policy with RAMALAMA_CONFIG=/dev/null", marks=[skip_if_no_container, skip_if_docker],
        ),
        pytest.param(
            ["--name", "foobar"], r".*--cap-drop=all", None, None, True,
            id="check if --cap-drop=all is present", marks=skip_if_no_container
        ),
        pytest.param(
            ["--name", "foobar"], r".*no-new-privileges", None, None, True,
            id="check if --no-new-privs is present", marks=skip_if_no_container),
        pytest.param(
            [], r".*--pull newer", None, None, True,
            id="check default pull policy", marks=[skip_if_no_container, skip_if_docker],
        ),
        pytest.param(
            ["--pull", "never"], r".*--pull never", None, None, True,
            id="check --pull never", marks=skip_if_no_container
        ),
        pytest.param(
            ["--privileged"], r".*--privileged", None, None, True,
            id="check --privileged", marks=skip_if_no_container
        ),
        pytest.param(
            ["--privileged"], r".*--cap-drop=all", None, None, False,
            id="check cap-drop=all is not set when --privileged", marks=skip_if_no_container
        ),
        pytest.param(
            ["--privileged"], r".*no-new-privileges", None, None, False,
            id="check no-new-privileges is not set when --privileged", marks=skip_if_no_container
        ),
        pytest.param(
            ["--selinux", "True"], r".*--security-opt=label=disable", None, None, False,
            id="check --selinux=True enables container separation", marks=skip_if_no_container),
        pytest.param(
            ["--selinux", "False"], r".*--security-opt=label=disable", None, None, True,
            id="check --selinux=False disables container separation", marks=skip_if_no_container),
        pytest.param(
            [], r".*--host 0.0.0.0", None, None, True,
            id="check default --host value to 0.0.0.0", marks=skip_if_container
        ),
        pytest.param(
            [], r".*--cache-reuse 256", None, None, True,
            id="check --cache-reuse default value", marks=skip_if_container
        ),
        pytest.param(
            ["--host", "127.0.0.1"],
            r".*--host 127.0.0.1", None, None, True,
            id="check --host flag to 127.0.0.1", marks=skip_if_container
        ),
        pytest.param(
            ["--seed", "abcd"],
            r".*--seed abcd", None, None, True,
            id="check --seed flag is set", marks=skip_if_container
        ),
        pytest.param(
            ["--detach"], r".*-d .*", None, None, True,
            id="check ---detach", marks=skip_if_no_container
        ),
        pytest.param(
            ["-d"], r".*-d .*", None, None, True,
            id="check -d", marks=skip_if_no_container
        ),
        pytest.param(
            ["--runtime-args", "--foo -bar"], r".*--foo\s+-bar", None, None, True,
            id="check --runtime-args"
        ),
        pytest.param(
            ["--runtime-args", "--foo='a b c'"], r".*--foo=a b c", None, None, True,
            id="check --runtime-args=\"--foo='a b c'\""
        ),
        pytest.param(
            ["--thinking", "False"], r".*--reasoning-budget 0", None, None, True,
            id="check --reasoning-budget 0 passed to runtime",
        ),
        pytest.param(
            [], r".*--reasoning-budget", None, None, False,
            id="check --reasoning-budget not passed by default",
        ),
    ],
)
# fmt: on
def test_params(extra_params, pattern, config, env_vars, expected):
    with RamalamaExecWorkspace(config=config, env_vars=env_vars) as ctx:
        result = ctx.check_output(RAMALAMA_DRY_RUN + extra_params + [DRY_RUN_TEST_MODEL])
        assert bool(re.search(pattern, result)) is expected


# fmt: off
@pytest.mark.e2e
@pytest.mark.parametrize(
    "extra_params, pattern, config, env_vars, expected_exit_code, expected",
    [
        pytest.param(
            ["--pull", "bogus"], r".*error: argument --pull: invalid choice: 'bogus'", None, None, 2, True,
            id="raise error when --pull value is not valid", marks=skip_if_no_container,
        ),
        pytest.param(
            ["--runtime-args", "--foo='a b c"], r".*No closing quotation", None, None, 22, True,
            id="raise closing quotation error with --runtime-args",
        ),
        pytest.param(
            ["--selinux", "100"], r".*Error: Cannot coerce '100' to bool", None, None, 22, True,
            id="raise error when --selinux has non boolean value", marks=skip_if_no_container,
        )
    ],
)
# fmt: on
def test_params_errors(extra_params, pattern, config, env_vars, expected_exit_code, expected):
    with RamalamaExecWorkspace(config=config, env_vars=env_vars) as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(RAMALAMA_DRY_RUN + extra_params + [DRY_RUN_TEST_MODEL], stderr=STDOUT)
        assert exc_info.value.returncode == expected_exit_code
        assert bool(re.search(pattern, exc_info.value.output.decode("utf-8"))) is expected


@pytest.mark.e2e
def test_non_existing_model():
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(["ramalama", "serve", "NON_EXISTING_MODEL"], stderr=STDOUT)
        assert exc_info.value.returncode == 22
        assert re.search(
            r".*Error: Manifest for NON_EXISTING_MODEL:latest was not found in the Ollama registry",
            exc_info.value.output.decode("utf-8"),
        )


@pytest.mark.e2e
@skip_if_container
def test_nocontainer_and_name_flag_conflict():
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(["ramalama", "--nocontainer", "serve", "--name", "foobar", "tiny"], stderr=STDOUT)
        assert exc_info.value.returncode == 22
        assert re.search(
            r".*Error: --nocontainer and --name options conflict. The --name option requires a container.",
            exc_info.value.output.decode("utf-8"),
        )


@pytest.mark.e2e
@skip_if_no_container
def test_full_model_name_expansion():
    result = check_output(RAMALAMA_DRY_RUN + ["smollm"])
    pattern = ".*ai.ramalama.model=ollama://library/smollm:latest"
    assert re.search(pattern, result)


@pytest.mark.e2e
@skip_if_no_container
def test_serve_and_stop(shared_ctx, test_model):
    ctx = shared_ctx
    container1_id = f"serve_and_stop_{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"
    container2_id = f"serve_and_stop_{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"

    # Serve Container1
    ctx.check_call(["ramalama", "serve", "--name", container1_id, "--detach", test_model])

    # FIXME: race-condition, chat can fail to connect if llama.cpp isn't ready, just sleep a little for now
    time.sleep(10)

    try:
        info = json.loads(ctx.check_output(["ramalama", "info"]))
        full_model_name = info["Shortnames"]["Names"][test_model]

        ps_result = ctx.check_output(["ramalama", "ps"])
        assert re.search(f".*{container1_id}", ps_result)

        ps_list = ctx.check_output(["ramalama", "ps", "--format", "{{.Names}} {{.Ports}}"])
        port = re.search(rf"{container1_id}.*->(?P<port>\d+)", ps_list)["port"]

        chat_result = ctx.check_output(["ramalama", "chat", "--ls", "--url", f"http://127.0.0.1:{port}/v1"]).strip()
        assert chat_result == full_model_name.split("://")[-1]

        containers_list = ctx.check_output(["ramalama", "containers", "--noheading"])
        assert re.search(f".*{container1_id}", containers_list)
    finally:
        # Stop Container1
        ctx.check_call(["ramalama", "stop", container1_id])

    # Start Container2
    c2_id = ctx.check_output(["ramalama", "serve", "--name", container2_id, "-d", test_model]).split("\n")[0]
    try:
        containers_list = check_output(["ramalama", "containers", "-n"])
        assert re.search(f".*{c2_id[:10]}", containers_list)

        ps_result = ctx.check_output(["ramalama", "ps", "--noheading", "--no-trunc"])
        assert re.search(f".*{container2_id}", ps_result)
    finally:
        # Stop Container2
        ctx.check_call(["ramalama", "stop", container2_id])

    # Check if both containers are stopped
    ps_result = ctx.check_output(["ramalama", "ps", "--noheading", "--no-trunc"])
    assert not re.search(f".*({container1_id}|{container2_id})", ps_result)


@pytest.mark.e2e
@skip_if_no_container
def test_serve_multiple_models(shared_ctx, test_model):
    ctx = shared_ctx
    container1_id = f"serve_multiple_{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"
    container2_id = f"serve_multiple_{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"
    container1_port = random.randint(64000, 65000)
    container2_port = random.randint(64000, 65000)
    while container1_port == container2_port:
        container2_port = random.randint(64000, 65000)

    # Start both models
    ctx.check_call(
        ["ramalama", "serve", "--name", container1_id, "--port", str(container1_port), "--detach", test_model]
    )
    ctx.check_call(
        ["ramalama", "serve", "--name", container2_id, "--port", str(container2_port), "--detach", test_model]
    )

    # Check if they are up
    ps_result = check_output(["ramalama", "ps", "--noheading"])
    assert re.search(f".*{container1_port}/tcp.*{container1_id}", ps_result)
    assert re.search(f".*{container2_port}/tcp.*{container2_id}", ps_result)

    # Stop both models
    ctx.check_call(["ramalama", "stop", container1_id])
    ctx.check_call(["ramalama", "stop", container2_id])

    # Check if they are stopped
    ps_result = check_output(["ramalama", "ps", "--noheading"])
    assert not re.search(f".*({container1_id}|{container2_id})", ps_result)


@pytest.mark.e2e
@skip_if_no_container
def test_stop_failures():
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(["ramalama", "stop"], stderr=STDOUT)
        assert exc_info.value.returncode == 22
        assert re.search(r"Error: must specify a container name", exc_info.value.output.decode("utf-8"))

        with pytest.raises(CalledProcessError) as exc_info:
            container_id = f"stop_failure_{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"
            ctx.check_output(["ramalama", "stop", container_id], stderr=STDOUT)
        assert re.search(r"Error.*such container.*", exc_info.value.output.decode("utf-8"))

        container_id = f"stop_failure_{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"
        ctx.check_call(["ramalama", "stop", "--ignore", container_id], stderr=STDOUT)

        with pytest.raises(CalledProcessError) as exc_info:
            container_id = f"stop_failure_{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"
            ctx.check_output(["ramalama", "stop", "--all", container_id], stderr=STDOUT)
        assert exc_info.value.returncode == 22
        assert re.search(
            fr"Error: specifying --all and container name, {container_id}, not allowed",
            exc_info.value.output.decode("utf-8"),
        )


@pytest.mark.e2e
def test_quadlet_generation(shared_ctx, test_model):
    ctx = shared_ctx
    test_model_full_name = get_full_model_name(test_model)
    container_file = Path(ctx.workspace_dir) / f"{test_model_full_name}.container"
    ctx.check_call(
        ["ramalama", "serve", "--port", "1234", "--pull", "never", "--generate", "quadlet", test_model],
        env={"HIP_VISIBLE_DEVICES": "99"},
    )
    with container_file.open("r") as f:
        content = f.read()
        assert re.search(r".*PublishPort=0.0.0.0:1234:1234", content)
        assert re.search(r".*llama-server --host 0.0.0.0 --port 1234 --model .*", content)
        assert re.search(f".*Mount=type=bind,.*{test_model_full_name}", content)
        assert re.search(r".*Environment=HIP_VISIBLE_DEVICES=99", content)


@pytest.mark.e2e
def test_quadlet_generation_with_add_to_unit_flag(test_model):
    with RamalamaExecWorkspace() as ctx:
        test_model_full_name = get_full_model_name(test_model)
        container_file = Path(ctx.workspace_dir) / f"{test_model_full_name}.container"
        ctx.check_call(
            ["ramalama", "serve", "--generate", "quadlet", "--add-to-unit", "section1:key0:value0", test_model]
        )
        with container_file.open("r") as f:
            content = f.read()
            assert re.search(r".*key0=value0.*", content)


@pytest.mark.e2e
def test_generation_with_bad_id(test_model):
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(["ramalama", "serve", "--port", "1234", "--generate", "bogus", test_model], stderr=STDOUT)
        assert exc_info.value.returncode == 2
        assert re.search(
            r".*error: argument --generate: invalid choice: .*bogus.* \(choose from .*\)",
            exc_info.value.output.decode("utf-8"),
        )


@pytest.mark.e2e
def test_generation_with_bad_add_to_unit_flag_value(test_model):
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(
                [
                    "ramalama",
                    "serve",
                    "--port",
                    "1234",
                    "--generate",
                    "quadlet",
                    "--add-to-unit",
                    "section1:key0:",
                    test_model,
                ],
                stderr=STDOUT,
            )
        assert exc_info.value.returncode == 2
        assert re.search(
            r".*error: --add-to-unit parameters must be of the form <section>:<key>:<value>.*",
            exc_info.value.output.decode("utf-8"),
        )


@pytest.mark.e2e
@skip_if_no_container
@pytest.mark.xfail("config.option.container_engine == 'docker'", reason="docker login does not support --tls-verify")
def test_quadlet_and_kube_generation_with_container_registry(container_registry, is_container, test_model):
    with RamalamaExecWorkspace() as ctx:
        authfile = (Path(ctx.workspace_dir) / "authfile.json").as_posix()
        auth_flags = ["--authfile", authfile, "--tls-verify", "false"]
        credential_flags = ["--username", container_registry.username, "--password", container_registry.password]
        test_image_url = f"{container_registry.url}/{test_model}"
        container_name = f"quadlet_gen_{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"
        container_port = random.randint(64000, 65000)

        # Login to the container registry with ramalama
        ctx.check_call(["ramalama", "login"] + auth_flags + credential_flags + [container_registry.url])

        # Pull test model
        ctx.check_call(["ramalama", "pull", test_model])

        # Push test model to the container registry in different modes
        for model_type_flag in [[], ["--type=car"], ["--type=raw"]]:
            ctx.check_call(["ramalama", "push"] + model_type_flag + auth_flags + [test_model, test_image_url])

        # Generate a quadlet
        result = ctx.check_output(
            ["ramalama", "serve"]
            + auth_flags
            + ["--name", container_name, "--port", str(container_port), "--generate", "quadlet", test_image_url]
        )
        assert re.search(".*Generating quadlet file: {}.container".format(container_name), result)
        assert re.search(".*Generating quadlet file: {}.volume".format(container_name), result)
        assert re.search(".*Generating quadlet file: {}.image".format(container_name), result)

        # Inspect the generated quadlet file
        quadlet_file = Path(ctx.workspace_dir) / "{}.container".format(container_name)
        with quadlet_file.open("r") as f:
            content = f.read()
            assert re.search(f".*PublishPort=0.0.0.0:{container_port}:{container_port}", content)
            assert re.search(f".*ContainerName={container_name}", content)
            assert re.search(f".*Exec=.*llama-server --host 0.0.0.0 --port {container_port} --model .*", content)
            quadlet_image_source = f"{container_registry.host}:{container_registry.port}/{test_model}"
            assert re.search(
                f".*Mount=type=image,source={quadlet_image_source},"
                f"destination=/mnt/models,subpath=/models,readwrite=false",
                content,
            )

        # If container mode is enabled, inspect the volume & image files generated
        if is_container:
            quadlet_volume_file = Path(ctx.workspace_dir) / f"{container_name}.volume"
            with quadlet_volume_file.open("r") as f:
                content = f.read()
                assert re.search(r".*Driver=image", content)
                assert re.search(f".*Image={container_name}.image", content)

            quadlet_image_file = Path(ctx.workspace_dir) / f"{container_name}.image"
            with quadlet_image_file.open("r") as f:
                content = f.read()
                assert re.search(f".*Image={quadlet_image_source}", content)

        # Test kube generation with vllm runtime
        result = ctx.check_output(
            ["ramalama", "--runtime", "vllm", "serve", "--name", "test-generation", "--port", "1234"]
            + auth_flags
            + ["--generate", "kube", test_image_url]
        )
        assert re.search(r".*Generating Kubernetes YAML file: test-generation.yaml", result)
        kube_file = Path(ctx.workspace_dir) / "test-generation.yaml"
        assert kube_file.exists()
        kube_file.unlink()

        # Test quadlet/kube generation with vllm runtime
        result = ctx.check_output(
            ["ramalama", "--debug", "--runtime", "vllm", "serve", "--name", "test-generation", "--port", "1234"]
            + auth_flags
            + ["--generate", "quadlet/kube", test_image_url]
        )
        assert re.search(r".*Generating Kubernetes YAML file: test-generation.yaml", result)
        assert re.search(r".*Generating quadlet file: test-generation.kube", result)
        kube_file = Path(ctx.workspace_dir) / "test-generation.yaml"
        with kube_file.open("r") as f:
            content = yaml.safe_load(f.read())
            containers_spec = content.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
            assert len(containers_spec) == 1
            container_spec = containers_spec[0]
            assert 'command' not in container_spec
            model_alias = f"{container_registry.host}:{container_registry.port}/{test_model.split(':')[0]}"
            assert container_spec['args'] == [
                "--model",
                "/mnt/models/model.file",
                "--served-model-name",
                f"{model_alias}",
                "--port",
                "1234",
            ]
            volumes_spec = content.get("spec", {}).get("template", {}).get("spec", {}).get("volumes", [])
            assert volumes_spec[0] == {
                "name": "model",
                "image": {
                    "reference": f"{container_registry.host}:{container_registry.port}/{test_model}",
                    "pullPolicy": "IfNotPresent",
                },
            }


@pytest.mark.e2e
@pytest.mark.parametrize(
    "generate, env_vars",
    [
        pytest.param(
            *item,
            id=f"generate={item[0]}{' + env_vars' if item[1] else ''}",
        )
        for item in itertools.product(
            [
                "kube",
                "kube:{tmp_dir}{sep}output",
                "quadlet/kube",
                "quadlet/kube:{tmp_dir}{sep}output",
                "compose",
                "compose:{tmp_dir}{sep}output",
            ],
            [None, {"HIP_VISIBLE_DEVICES": "99"}],
        )
    ],
)
def test_serve_kube_generation(test_model, generate, env_vars):
    with RamalamaExecWorkspace(env_vars=env_vars) as ctx:
        # Pull model
        ctx.check_call(["ramalama", "pull", test_model])

        # Define the output dir if it's required and ensure it is created
        output_dir = (
            Path(ctx.workspace_dir) / "output"
            if generate.endswith(":{tmp_dir}{sep}output")
            else Path(ctx.workspace_dir)
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        # Exec ramalama serve
        result = ctx.check_output(
            [
                "ramalama",
                "serve",
                "--name",
                "test",
                "--port",
                "1234",
                "--pull",
                "never",
                "--generate",
                generate.format(tmp_dir=ctx.workspace_dir, sep=os.sep),
                test_model,
            ]
        )

        with chdir(output_dir):
            # Test the expected output of the command execution
            if "kube" in generate:
                generated_file = output_dir / "test.yaml"
                assert re.search(r".*Generating Kubernetes YAML file: test.yaml", result)
                if generate.startswith("quadlet/kube"):
                    assert re.search(r".*Generating quadlet file: test.kube", result)
            elif "compose" in generate:
                generated_file = output_dir / "docker-compose.yaml"
                assert re.search(r".*Generating Compose YAML file: docker-compose.yaml", result)
            else:
                raise Exception("Invalid generate option")

            # Check "test.yaml" contents
            with generated_file.open("r") as f:
                content = f.read()
                if "kube" in generate:
                    assert re.search(r".*command: \[\".*serve.*\"]", content)
                    assert re.search(r".*containerPort: 1234", content)
                elif "compose" in generate:
                    assert re.search(r".*command: .*serve.*", content)
                    assert re.search(r".*ports:", content)
                    assert re.search(r".*- \"1234:1234\"", content)
                else:
                    raise Exception("Invalid generate option")

                if env_vars:
                    if "kube" in generate:
                        assert re.search(r".*env:", content)
                        assert re.search(r".*name: HIP_VISIBLE_DEVICES", content)
                        assert re.search(r".*value: \"99\"", content)
                    elif "compose" in generate:
                        assert re.search(r".*environment:", content)
                        assert re.search(r".*- HIP_VISIBLE_DEVICES=99", content)
                    else:
                        raise Exception("Invalid generate option")

            # Check "test.kube" contents if generate="quadlet/kube"
            if generate.startswith("quadlet/kube"):
                with (output_dir / "test.kube").open("r") as f:
                    content = f.read()
                    assert re.search(r".*Yaml=test.yaml", content)


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
def test_kube_generation_with_llama_api(test_model):
    with RamalamaExecWorkspace() as ctx:
        # Pull model
        ctx.check_call(["ramalama", "pull", test_model])

        # Exec ramalama serve
        result = ctx.check_output(
            [
                "ramalama",
                "serve",
                "--name",
                "test",
                "--port",
                "1234",
                "--generate",
                "kube",
                "--api",
                "llama-stack",
                "--dri",
                "off",
                test_model,
            ]
        )

        # Test the expected output of the command execution
        assert re.search(r".*Generating Kubernetes YAML file: test.yaml", result)

        # Check "test.yaml" contents
        with (Path(ctx.workspace_dir) / "test.yaml").open("r") as f:
            content = f.read()
            assert re.search(r".*llama-server", content)
            assert re.search(r".*hostPort: 1234", content)
            assert re.search(r".*/llama-stack", content)


@pytest.mark.skip(reason="pulls very large image")
@pytest.mark.e2e
@skip_if_docker
@skip_if_no_container
@skip_if_ppc64le
@skip_if_s390x
def test_serve_api(caplog):
    # Configure logging for requests
    caplog.set_level(logging.CRITICAL, logger="requests")
    caplog.set_level(logging.CRITICAL, logger="urllib3")
    test_model = "tiny"

    with RamalamaExecWorkspace() as ctx:
        # Pull model
        ctx.check_call(["ramalama", "pull", test_model])

        # Serve an API
        container_name = f"api{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"
        container_port = random.randint(64000, 65000)

        result = ctx.check_output(
            [
                "ramalama",
                "serve",
                "-d",
                "--name",
                container_name,
                "--port",
                str(container_port),
                "--api",
                "llama-stack",
                "--dri",
                "off",
                test_model,
            ],
            stderr=STDOUT,
        )

        assert re.search(fr".*Llama Stack RESTAPI: http://localhost:{container_port}", result)
        assert re.search(fr".*OpenAI RESTAPI: http://localhost:{container_port}/v1/openai", result)

        # Inspect the models API
        # FIXME: llama-stack image is currently broken.
        # models = requests.get(f"http://localhost:{container_port}/models").json()
        # assert models["models"][0]["name"] == test_model
        # assert models["models"][0]["model"] == test_model

        # Stop container
        ctx.check_call(["ramalama", "stop", container_name])


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_gh_actions_darwin
def test_serve_with_non_existing_images():
    with RamalamaExecWorkspace() as ctx:
        # If the requested model is missing, "ramalama serve --pull never" will exit with
        # "Error: <model> does not exist" and returncode 22. To test the behavior of a
        # non-existent image reference, the requested model must already be available locally.
        ctx.check_call(["ramalama", "pull", "tiny"])
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(["ramalama", "serve", "--image", "bogus", "--pull", "never", "tiny"], stderr=STDOUT)
        assert exc_info.value.returncode == 125
        assert re.search(r".*Error: bogus: image not known", exc_info.value.output.decode("utf-8"))

        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(
                [
                    "ramalama",
                    "serve",
                    "--image",
                    "bogus1",
                    "--rag",
                    "quay.io/ramalama/rag",
                    "--pull",
                    "never",
                    "tiny",
                ],
                stderr=STDOUT,
            )
        assert exc_info.value.returncode == 22
        assert re.search(r"Error: quay.io/ramalama/rag does not exist.*", exc_info.value.output.decode("utf-8"))


@pytest.mark.e2e
@skip_if_no_container
@skip_if_darwin
@skip_if_docker
def test_serve_with_rag():
    with RamalamaExecWorkspace() as ctx:
        result_a = ctx.check_output(RAMALAMA_DRY_RUN + ["--rag", "quay.io/ramalama/rag", "--pull", "never", "tiny"])
        assert re.search(r".*llama-server", result_a)
        assert re.search(r".*quay.io/.*-rag(@sha256)?:", result_a)
        assert re.search(r".*rag_framework serve", result_a)
        assert re.search(r".*--mount=type=image,source=quay.io/ramalama/rag,destination=/rag,rw=true", result_a)

        result_b = ctx.check_output(
            [
                "ramalama",
                "--dryrun",
                "serve",
                "--image",
                "quay.io/ramalama/ramalama:1.0",
                "--rag",
                "quay.io/ramalama/rag",
                "--pull",
                "never",
                "tiny",
            ]
        )
        assert re.search(r".*quay.io/ramalama/ramalama:1.0", result_b)

        result_c = ctx.check_output(
            [
                "ramalama",
                "--dryrun",
                "serve",
                "--rag",
                "quay.io/ramalama/rag",
                "--rag-image",
                "quay.io/ramalama/ramalama-rag:1.0",
                "--pull",
                "never",
                "tiny",
            ]
        )
        assert re.search(r".*quay.io/ramalama/ramalama-rag:1.0", result_c)
