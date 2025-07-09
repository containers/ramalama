import itertools
import json
import logging
import random
import re
import string
from contextlib import chdir
from pathlib import Path
from subprocess import STDOUT, CalledProcessError
from test.conftest import (
    skip_if_container,
    skip_if_darwin,
    skip_if_docker,
    skip_if_gh_actions_darwin,
    skip_if_no_container,
    skip_if_not_darwin,
)
from test.e2e.utils import RamalamaExecWorkspace, check_call, check_output

import pytest

TEST_MODEL = "smollm:135m"
RAMALAMA_DRY_RUN = ["ramalama", "-q", "--dryrun", "serve"]


@pytest.mark.e2e
@skip_if_no_container
def test_basic_dry_run():
    ramalama_info = json.loads(check_output(["ramalama", "info"]))

    result = check_output(f"ramalama -q --dryrun serve {TEST_MODEL}", shell=True)
    assert result.startswith("{} run --rm".format(ramalama_info["Engine"]["Name"]))
    assert not re.search(r".*-t -i", result), "run without terminal"


@pytest.mark.e2e
@pytest.mark.parametrize(
    "extra_params, pattern, config, env_vars, expected",
    [
        # fmt: off
        pytest.param(
            [], f".*{TEST_MODEL}.*", None, None, True,
            id="check test_model", marks=skip_if_no_container
        ),
        pytest.param(
            [], r".*--name ramalama_.", None, None, True,
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
        # FIXME: This e2e is not working because something has changed in the code
        # pytest.param(
        #     ["--name", "foobar"], r".*--host 0.0.0.0", None, None, False,
        #     id="check --host is not present when run within container", marks=skip_if_no_container
        # ),
        pytest.param(
            ["--name", "foobar"], f".*{TEST_MODEL}.*", None, None, True,
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
            None, {"RAMALAMA_CONFIG": "/dev/null"}, True,
            id="check --seed 1234 with RAMALAMA_CONFIG=/dev/null", marks=skip_if_no_container,
        ),
        pytest.param(
            ["--name", "foobar"], r"..*--pull newer", None, {"RAMALAMA_CONFIG": "/dev/null"}, True,
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
            # FIXME
            [], r".*--pull missing", None, None, True,
            id="check missing pull policy", marks=[skip_if_no_container, pytest.mark.xfail(reason="missing")],
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
            ["--runtime-args", "--foo -bar"], r".*--foo\s+-bar", None, None, True,
            id="check --runtime-args", marks=skip_if_no_container
        ),
        pytest.param(
            ["--runtime-args", "--foo='a b c'"], r".*--foo=a b c", None, None, True,
            id="check --runtime-args=\"--foo='a b c'\"", marks=skip_if_no_container
        ),
        pytest.param(
            [], r".*--cache-reuse 256", None, None, True,
            id="check --cache-reuse default value"
        ),
        pytest.param(
            [], r".*--flash-attn", None, None, True,
            id="check --flash-attn", marks=[skip_if_container, skip_if_not_darwin]
        ),
        pytest.param(
            ["--detach"], r".*-d .*", None, None, True,
            id="check ---detach", marks=skip_if_no_container
        ),
        pytest.param(
            ["-d"], r".*-d .*", None, None, True,
            id="check -d", marks=skip_if_no_container
        ),
        # fmt: on
    ],
)
def test_params(extra_params, pattern, config, env_vars, expected):
    with RamalamaExecWorkspace(config=config, env_vars=env_vars) as ctx:
        result = ctx.check_output(RAMALAMA_DRY_RUN + extra_params + [TEST_MODEL])
        assert bool(re.search(pattern, result)) is expected


@pytest.mark.e2e
@pytest.mark.parametrize(
    "extra_params, pattern, config, env_vars, expected_exit_code, expected",
    [
        # fmt: off
        pytest.param(
            ["--pull", "bogus"], r".*error: argument --pull: invalid choice: 'bogus'", None, None, 2, True,
            id="raise error when --pull value is not valid", marks=skip_if_no_container,
        ),
        pytest.param(
            ["--runtime-args", "--foo='a b c"], r".*No closing quotation", None, None, 1, True,
            id="raise closing quotation error with --runtime-args",
        ),
        # fmt: on
    ],
)
def test_params_errors(extra_params, pattern, config, env_vars, expected_exit_code, expected):
    with RamalamaExecWorkspace(config=config, env_vars=env_vars) as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(RAMALAMA_DRY_RUN + extra_params + [TEST_MODEL], stderr=STDOUT)
        assert exc_info.value.returncode == expected_exit_code
        assert bool(re.search(pattern, exc_info.value.output.decode("utf-8"))) is expected


@pytest.mark.e2e
def test_non_existing_model():
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(["ramalama", "serve", "NON_EXISTING_MODEL"], stderr=STDOUT)
        assert exc_info.value.returncode == 1
        assert re.search(
            r".*Error: Manifest for NON_EXISTING_MODEL:latest was not found in the Ollama registry",
            exc_info.value.output.decode("utf-8"),
        )


@pytest.mark.e2e
@skip_if_container
def test_nocontainer_and_name_flag_conflict():
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(["ramalama", "serve", "--name", "foobar", "tiny"], stderr=STDOUT)
        assert exc_info.value.returncode == 1
        assert re.search(
            r".*Error: --nocontainer and --name options conflict. The --name option requires a container.",
            exc_info.value.output.decode("utf-8"),
        )


@pytest.mark.e2e
@skip_if_no_container
@pytest.mark.xfail("config.option.container_engine == 'docker'", reason="docker ps does not support --noheading")
def test_serve_and_stop():
    container1_id = f"serve_and_stop_{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"
    container2_id = f"serve_and_stop_{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"

    # Serve Container1
    c1_id = check_output(["ramalama", "serve", "--name", container1_id, "--detach", TEST_MODEL]).split("\n")[0]
    ramalama_info = json.loads(check_output(["ramalama", "info"]))
    check_call([ramalama_info["Engine"]["Name"], "inspect", c1_id])

    # Check Container1 info
    ps1_result = check_output(["ramalama", "ps"])
    assert re.search(f".*{container1_id}", ps1_result)
    cnh1_result = check_output(["ramalama", "containers", "--noheading"])
    assert re.search(f".*{container1_id}", cnh1_result)

    # Stop Container1
    check_call(["ramalama", "stop", container1_id])

    # Start Container2
    c2_id = check_output(["ramalama", "serve", "--name", container2_id, "-d", TEST_MODEL]).split("\n")[0]

    # Check Container2 info
    ps2_result = check_output(["ramalama", "ps", "--noheading", "--no-trunc"])
    assert re.search(f".*{container2_id}", ps2_result)
    cnh2_result = check_output(["ramalama", "containers", "-n"])
    assert re.search(f".*{c2_id[:10]}", cnh2_result)

    # Stop Container2
    check_call(["ramalama", "stop", container2_id])

    # Check if both containers are stopped
    ps_result = check_output(["ramalama", "ps", "--noheading", "--no-trunc"])
    assert not re.search(f".*({container1_id}|{container2_id})", ps_result)


@pytest.mark.e2e
@skip_if_no_container
@pytest.mark.xfail("config.option.container_engine == 'docker'", reason="docker ps does not support --noheading")
def test_serve_multiple_models():
    container1_id = f"serve_multiple_{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"
    container2_id = f"serve_multiple_{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"
    container1_port, container2_port = random.sample(range(64000, 65000), 2)

    # Start both models
    check_call(["ramalama", "serve", "--name", container1_id, "--port", str(container1_port), "--detach", TEST_MODEL])
    check_call(["ramalama", "serve", "--name", container2_id, "--port", str(container2_port), "--detach", TEST_MODEL])

    # Check if they are up
    ps_result = check_output(["ramalama", "ps", "--noheading"])
    assert re.search(f".*{container1_port}/tcp.*{container1_id}", ps_result)
    assert re.search(f".*{container2_port}/tcp.*{container2_id}", ps_result)

    # Stop both models
    check_call(["ramalama", "stop", container1_id])
    check_call(["ramalama", "stop", container2_id])

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
            r"Error: specifying --all and container name, {}, not allowed".format(container_id),
            exc_info.value.output.decode("utf-8"),
        )


@pytest.mark.e2e
def test_quadlet_generation():
    with RamalamaExecWorkspace(env_vars={"HIP_VISIBLE_DEVICES": "99"}) as ctx:
        container_file = Path(ctx.workspace_dir) / f"{TEST_MODEL}.container"
        ctx.check_call(["ramalama", "serve", "--port", "1234", "--generate", "quadlet", TEST_MODEL])
        with container_file.open("r") as f:
            content = f.read()
            assert re.search(r".*PublishPort=1234:1234", content)
            assert re.search(r".*Exec=.*llama-server --port 1234 --model .*", content)
            assert re.search(f".*Mount=type=bind,.*{TEST_MODEL.split(':')[0]}", content)
            assert re.search(r".*Environment=HIP_VISIBLE_DEVICES=99", content)


@pytest.mark.e2e
def test_generation_with_bad_id():
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(["ramalama", "serve", "--port", "1234", "--generate", "bogus", TEST_MODEL], stderr=STDOUT)
        assert exc_info.value.returncode == 2
        assert re.search(
            r".*error: argument --generate: invalid choice: .*bogus.*", exc_info.value.output.decode("utf-8")
        )


@pytest.mark.e2e
@skip_if_no_container
@pytest.mark.xfail("config.option.container_engine == 'docker'", reason="docker login does not support --tls-verify")
def test_quadlet_and_kube_generation_with_container_registry(container_registry, is_container):
    with RamalamaExecWorkspace() as ctx:
        authfile = (Path(ctx.workspace_dir) / "authfile.json").as_posix()
        auth_flags = ["--authfile", authfile, "--tls-verify", "false"]
        credential_flags = ["--username", container_registry.username, "--password", container_registry.password]
        test_image_url = container_registry.url + f"/{TEST_MODEL}"
        container_name = f"quadlet_gen_{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"
        container_port = random.randint(64000, 65000)

        # Login to the container registry with ramalama
        ctx.check_call(["ramalama", "login"] + auth_flags + credential_flags + [container_registry.url])

        # Pull test model
        ctx.check_call(["ramalama", "pull", TEST_MODEL])

        # Push test model to the container registry in different modes
        for model_type_flag in [[], ["--type=car"], ["--type=raw"]]:
            ctx.check_call(["ramalama", "push"] + model_type_flag + auth_flags + [TEST_MODEL, test_image_url])

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
            assert re.search(f".*PublishPort={container_port}:{container_port}", content)
            assert re.search(f".*ContainerName={container_name}", content)
            assert re.search(f".*Exec=.*llama-server --port {container_port} --model .*", content)
            quadlet_image_source = f"{container_registry.host}:{container_registry.port}/{TEST_MODEL}"
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
        with kube_file.open("r") as f:
            content = f.read()
            assert re.search(r".*command: \[\"--port\"]", content)
            assert re.search(
                r".*args: \['1234',\s+'--model',\s+'/mnt/models/{}',\s+'--max_model_len', '2048'".format(TEST_MODEL),
                content,
            )
            kube_image_ref = f"{container_registry.host}:{container_registry.port}/{TEST_MODEL}"
            assert re.search(f".*reference: {kube_image_ref}", content)
            assert re.search(r".*pullPolicy: IfNotPresent", content)

        # Test quadlet/kube generation with vllm runtime
        result = ctx.check_output(
            ["ramalama", "--runtime", "vllm", "serve", "--name", "test-generation", "--port", "1234"]
            + auth_flags
            + ["--generate", "quadlet/kube", test_image_url]
        )

        assert re.search(r".*Generating Kubernetes YAML file: test-generation.yaml", result)
        assert re.search(r".*Generating quadlet file: test-generation.kube", result)


@pytest.mark.e2e
@pytest.mark.parametrize(
    "generate, env_vars",
    [
        pytest.param(
            *item,
            id=f"generate={item[0]}{' + env_vars' if item[1] else ''}",
        )
        for item in itertools.product(
            ["kube", "kube:{tmp_dir}/output", "quadlet/kube", "quadlet/kube:{tmp_dir}/output"],
            [None, {"HIP_VISIBLE_DEVICES": "99"}],
        )
    ],
)
def test_serve_kube_generation(generate, env_vars):
    with RamalamaExecWorkspace(env_vars=env_vars) as ctx:
        # Pull model
        ctx.check_call(["ramalama", "pull", TEST_MODEL])

        # Define the output dir if it's required and ensure it is created
        output_dir = (
            Path(ctx.workspace_dir) / "output" if generate.endswith(":{tmp_dir}/output") else Path(ctx.workspace_dir)
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
                "--generate",
                generate.format(tmp_dir=ctx.workspace_dir),
                TEST_MODEL,
            ]
        )

        with chdir(output_dir):
            # Test the expected output of the command execution
            assert re.search(r".*Generating Kubernetes YAML file: test.yaml", result)
            if generate.startswith("quadlet/kube"):
                assert re.search(r".*Generating quadlet file: test.kube", result)

            # Check "test.yaml" contents
            with (output_dir / "test.yaml").open("r") as f:
                content = f.read()
                assert re.search(r".*command: \[\".*serve.*\"]", content)
                assert re.search(r".*containerPort: 1234", content)
                if env_vars:
                    assert re.search(r".*env:", content)
                    assert re.search(r".*name: HIP_VISIBLE_DEVICES", content)
                    assert re.search(r".*value: 99", content)

            # Check "test.kube" contents if generate="quadlet/kube"
            if generate.startswith("quadlet/kube"):
                with (output_dir / "test.kube").open("r") as f:
                    content = f.read()
                    assert re.search(r".*Yaml=test.yaml", content)


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
def test_kube_generation_with_llama_api():
    with RamalamaExecWorkspace() as ctx:
        # Pull model
        ctx.check_call(["ramalama", "pull", TEST_MODEL])

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
                TEST_MODEL,
            ]
        )

        # Test the expected output of the command execution
        assert re.search(r".*Generating Kubernetes YAML file: test.yaml", result)

        # Check "test.yaml" contents
        with (Path(ctx.workspace_dir) / "test.yaml").open("r") as f:
            content = f.read()
            assert re.search(r".*llama-server", content)
            assert re.search(r".*hostPort: 1234", content)
            assert re.search(r".*quay.io/ramalama/llama-stack", content)


@pytest.mark.e2e
@skip_if_docker
@skip_if_no_container
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

        ctx.check_call(
            [
                "ramalama",
                "serve",
                "-d",
                "--name",
                container_name,
                "--port",
                str(container_port),
                "--dri",
                "off",
                test_model,
            ],
        )

        # Inspect the models API
        # FIXME: Currently is no working
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
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(["ramalama", "--image", "bogus", "serve", "--pull", "never", "tiny"], stderr=STDOUT)
        assert exc_info.value.returncode == 125
        assert re.search(r".*Error: bogus: image not known", exc_info.value.output.decode("utf-8"))

        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(
                [
                    "ramalama",
                    "--image",
                    "bogus1",
                    "serve",
                    "--rag",
                    "quay.io/ramalama/testrag",
                    "--pull",
                    "never",
                    "tiny",
                ],
                stderr=STDOUT,
            )
        assert exc_info.value.returncode == 125
        assert re.search(r".*Error: bogus1: image not known", exc_info.value.output.decode("utf-8"))


@pytest.mark.e2e
@skip_if_no_container
@skip_if_darwin
@skip_if_docker
def test_serve_with_rag():
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(
                RAMALAMA_DRY_RUN + ["--rag", "quay.io/ramalama/rag", "--pull", "never", "tiny"], stderr=STDOUT
            )
        assert exc_info.value.returncode == 125
        assert re.search(r"Error: quay.io/ramalama/rag: image not known.*", exc_info.value.output.decode("utf-8"))

        result_a = ctx.check_output(RAMALAMA_DRY_RUN + ["--rag", "quay.io/ramalama/testrag", "--pull", "never", "tiny"])
        assert re.search(r".*quay.io/ramalama/.*-rag:", result_a)

        result_b = ctx.check_output(
            [
                "ramalama",
                "--dryrun",
                "--image",
                "quay.io/ramalama/ramalama:1.0",
                "serve",
                "--rag",
                "quay.io/ramalama/testrag",
                "--pull",
                "never",
                "tiny",
            ]
        )
        assert re.search(r".*quay.io/ramalama/ramalama:1.0", result_b)
