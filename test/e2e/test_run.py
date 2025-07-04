import json
import re
from subprocess import STDOUT, CalledProcessError
from test.conftest import (
    skip_if_container,
    skip_if_darwin,
    skip_if_docker,
    skip_if_gh_actions_darwin,
    skip_if_no_container,
)
from test.e2e.utils import RamalamaExecWorkspace, check_call, check_output

import pytest

TEST_MODEL = "smollm:135m"
RAMALAMA_DRY_RUN = ["ramalama", "-q", "--dryrun", "run"]
CONFIG_WITH_PULL_NEVER = """
[ramalama]
pull="never"
"""

RUN_PARAMETERS_ERRORS_TEST_CASES = [
    # desc -> test_case description, params -> (extra_params, pattern, conf, env_vars, expected_exit_code, expected)
    {
        "desc": "raise error if try to pull non existing image",
        "params": pytest.param(
            ["--pull", "bogus"],
            r".*error: argument --pull: invalid choice: 'bogus'",
            None,
            None,
            2,
            True,
            marks=skip_if_no_container,
        ),
    },
]


@pytest.mark.e2e
@skip_if_no_container
def test_basic_dry_run():
    ramalama_info = json.loads(check_output(["ramalama", "info"]))

    result = check_output(f"ramalama -q --dryrun run {TEST_MODEL}", shell=True)
    assert result.startswith("{} run --rm".format(ramalama_info["Engine"]["Name"]))
    assert not re.search(r".*-t -i", result), "run without terminal"

    result = check_output(f"ramalama -q --dryrun run {TEST_MODEL} \"what's up doc?\"", shell=True)
    assert result.startswith("{} run --rm".format(ramalama_info["Engine"]["Name"]))
    assert not re.search(r".*-t -i", result), "run without terminal"

    result = check_output(f"echo \"Test\" | ramalama -q --dryrun run {TEST_MODEL}", shell=True)
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
            [], r".*--ctx-size 2048", None, None, True,
            id="check --ctx-size default value is 2048", marks=skip_if_no_container
        ),
        pytest.param(
            [], r".*--seed", None, None, False,
            id="check --seed is not set by default", marks=skip_if_no_container
        ),
        pytest.param(
            [], r".*-t -i", None, None, False,
            id="check -t -i is not present without tty", marks=skip_if_no_container)
        ,
        pytest.param(
            ["--env", "a=b", "--env", "test=success", "--name", "foobar"],
            r"--env a=b --env test=success", None, None, True,
            id="check --env", marks=skip_if_no_container,
        ),
        pytest.param(
            ["--oci-runtime", "foobar"], r"--runtime foobar", None, None, True,
            id="check --oci-runtime", marks=skip_if_no_container)
        ,
        pytest.param(
            ["--net", "bridge", "--name", "foobar"], r".*--network bridge",
            None, {"RAMALAMA_CONFIG": "/dev/null"}, True,
            id="check --net=bridge with RAMALAMA_CONFIG=/dev/null", marks=skip_if_no_container,
        ),
        pytest.param(
            ["--name", "foobar"], f".*{TEST_MODEL}.*",
            None, {"RAMALAMA_CONFIG": "/dev/null"}, True,
            id="check test_model with RAMALAMA_CONFIG=/dev/null", marks=skip_if_no_container,
        ),
        pytest.param(
            ["-c", "4096", "--name", "foobar"], r".*--ctx-size 4096",
            None, {"RAMALAMA_CONFIG": "/dev/null"}, True,
            id="check --ctx-size 4096 with RAMALAMA_CONFIG=/dev/null",  marks=skip_if_no_container,
        ),
        pytest.param(
            ["--name", "foobar"], r".*--temp 0.8", None, {"RAMALAMA_CONFIG": "/dev/null"}, True,
            id="check --temp default value is 0.8 with RAMALAMA_CONFIG=/dev/null", marks=skip_if_no_container,
        ),
        pytest.param(
            ["--seed", "9876", "--name", "foobar"], r".*--seed 9876",
            None, {"RAMALAMA_CONFIG": "/dev/null"}, True,
            id="check --seed 9876 with RAMALAMA_CONFIG=/dev/null", marks=skip_if_no_container,
        ),
        pytest.param(
            ["--name", "foobar"], r"..*--pull newer", None, {"RAMALAMA_CONFIG": "/dev/null"}, True,
            id="check pull policy with RAMALAMA_CONFIG=/dev/null", marks=[skip_if_no_container, skip_if_docker],
        ),
        pytest.param(
            [], r".*--pull missing", None, None, True,
            id="check missing pull policy",
            marks=[skip_if_no_container, pytest.mark.xfail(reason="--pull missing is missing")],
        ),
        pytest.param(
            ["--pull", "never", "-c", "4096", "--name", "foobbar"], r".*--pull never", None, None, True,
            id="check never pull policy", marks=skip_if_no_container,
        ),
        pytest.param(
            [], r".*--pull never", CONFIG_WITH_PULL_NEVER, None, True,
            id="check pull policy with RAMALAMA_CONFIG", marks=skip_if_no_container
        ),
        pytest.param(
            ["--name", "foobar"], r".*--name foobar", None, None, True,
            id="check --name foobar", marks=skip_if_no_container
        ),
        pytest.param(
            ["--name", "foobar"], r".*--cap-drop=all", None, None, True,
            id="check if --cap-drop=all is present", marks=skip_if_no_container
        ),
        pytest.param(
            ["--name", "foobar"], r".*no-new-privileges", None, None, True,
            id="check if --no-new-privs is present", marks=skip_if_no_container),
        pytest.param(
            ["--runtime-args", "--foo -bar"], r".*--foo\s+-bar", None, None, True,
            id="check --runtime-args", marks=skip_if_no_container
        ),
        pytest.param(
            ["--runtime-args", "--foo='a b c'"], r".*--foo=a b c", None, None, True,
            id="check --runtime-args=\"--foo='a b c'\"", marks=skip_if_no_container
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
            [], r".*foo:latest..*serve", None, {"RAMALAMA_IMAGE": "foo:latest"}, True,
            id="check run with RAMALAMA_IMAGE=foo:latest", marks=skip_if_no_container
        ),
        pytest.param(
            ["--ctx-size", "4096"], r".*serve.*--ctx-size 4096 --temp 0.8.*", None, None, True,
            id="check --ctx-size 4096 & --temp 0.8.*", marks=skip_if_container,
        ),
        pytest.param(
            [], r".*-e ASAHI_VISIBLE_DEVICES=99", None, {"ASAHI_VISIBLE_DEVICES": "99"}, True,
            id="check ASAHI_VISIBLE_DEVICES env var", marks=skip_if_no_container,
        ),
        pytest.param(
            [], r".*-e CUDA_LAUNCH_BLOCKING=1", None, {"CUDA_LAUNCH_BLOCKING": "1"}, True,
            id="check CUDA_LAUNCH_BLOCKING env var", marks=skip_if_no_container
        ),
        pytest.param(
            [], r".*-e HSA_OVERRIDE_GFX_VERSION=0.0.0", None, {"HSA_OVERRIDE_GFX_VERSION": "0.0.0"}, True,
            id="check HSA_OVERRIDE_GFX_VERSION env var", marks=skip_if_no_container,
        ),
        pytest.param(
            [], r".*-e HIP_VISIBLE_DEVICES=99", None, {"HIP_VISIBLE_DEVICES": "99"}, True,
            id="check HIP_VISIBLE_DEVICES env var", marks=skip_if_no_container
        ),
        pytest.param(
            [], r"(.*-e (HIP_VISIBLE_DEVICES=99|HSA_OVERRIDE_GFX_VERSION=0.0.0)){2}",
            None, {"HIP_VISIBLE_DEVICES": "99", "HSA_OVERRIDE_GFX_VERSION": "0.0.0"}, True,
            id="check HIP_VISIBLE_DEVICES & HSA_OVERRIDE_GFX_VERSION env vars", marks=skip_if_no_container,
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
            id="raise closing quotation error with --runtime-args", marks=skip_if_no_container,
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
def test_run_model_with_prompt():
    check_call(
        ["ramalama", "run", "--temp", "0", TEST_MODEL, "What is the first line of the declaration of independence?"]
    )


@pytest.mark.e2e
def test_run_keepalive():
    check_call(["ramalama", "run", "--keepalive", "1s", "tiny"])


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_gh_actions_darwin
def test_run_with_non_existing_images():
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(["ramalama", "--image", "bogus", "run", "--pull", "never", "tiny"], stderr=STDOUT)
        assert exc_info.value.returncode == 22
        assert re.search(r".*Error: bogus: image not known", exc_info.value.output.decode("utf-8"))

        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(
                [
                    "ramalama",
                    "--image",
                    "bogus1",
                    "run",
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
def test_run_with_rag():
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
                "run",
                "--rag",
                "quay.io/ramalama/testrag",
                "--pull",
                "never",
                "tiny",
            ]
        )
        assert re.search(r".*quay.io/ramalama/ramalama:1.0", result_b)
