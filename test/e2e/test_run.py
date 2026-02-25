import json
import platform
import re
import shutil
from pathlib import Path
from subprocess import DEVNULL, PIPE, STDOUT, CalledProcessError

import pytest

from test.conftest import (
    skip_if_container,
    skip_if_darwin,
    skip_if_docker,
    skip_if_gh_actions_darwin,
    skip_if_no_container,
    skip_if_not_windows,
)
from test.e2e.utils import RamalamaExecWorkspace, check_output

TEST_MODEL = "smollm:135m"
TEST_MODEL_FULL_NAME = "smollm-135M-instruct-v0.2-Q8_0-GGUF"

RAMALAMA_DRY_RUN = ["ramalama", "-q", "--dryrun", "run"]
CONFIG_WITH_PULL_NEVER = """
[ramalama]
pull="never"
"""
DEFAULT_PULL_PATTERN = r".*--pull (?:always|newer)"

WSL_TMP_DIR = r'\\wsl.localhost\podman-machine-default\var\tmp'


@pytest.fixture(scope="module")
def shared_ctx_with_models(test_model):
    config = """
    [ramalama]
    store="{workspace_dir}/.local/share/ramalama"
    """
    with RamalamaExecWorkspace(config=config) as ctx:
        ctx.check_call(["ramalama", "-q", "pull", test_model])
        ctx.check_call(["ramalama", "-q", "pull", "tiny"])
        yield ctx


@pytest.mark.e2e
@skip_if_no_container
def test_basic_dry_run():
    ramalama_info = json.loads(check_output(["ramalama", "info"]))
    conman = ramalama_info["Engine"]["Name"]

    result = check_output(["ramalama", "-q", "--dryrun", "run", TEST_MODEL], stdin=PIPE)
    assert not result.startswith(f"{conman} run --rm")
    assert not re.search(r".*-t -i", result), "run without terminal"

    result = check_output(["ramalama", "-q", "--dryrun", "run", TEST_MODEL, "what's up doc?"], stdin=PIPE)
    assert result.startswith(f"{conman} run")
    assert not re.search(r".*-t -i", result), "run without terminal"

    result = check_output(f'echo "Test" | ramalama -q --dryrun run {TEST_MODEL}', shell=True, stdin=PIPE)
    assert result.startswith(f"{conman} run")
    assert not re.search(r".*-t -i", result), "run without terminal"


# fmt: off
@pytest.mark.e2e
@pytest.mark.parametrize(
    "extra_params, pattern, config, env_vars, expected, stdin",
    [
        pytest.param(
            [], f".*{TEST_MODEL_FULL_NAME}.*", None, None, True, None,
            id="check test_model", marks=skip_if_no_container
        ),
        pytest.param(
            [], r".*--cache-reuse 256", None, None, True, None,
            id="check cache-reuse is being set", marks=skip_if_no_container
        ),
        pytest.param(
            [], r".*--ctx-size", None, None, False, None,
            id="check ctx-size is not show by default", marks=skip_if_no_container
        ),
        pytest.param(
            [], r".*--seed", None, None, False, None,
            id="check --seed is not set by default", marks=skip_if_no_container
        ),
        pytest.param(
            [], r".*-t -i",None, None, False, PIPE,
            id="check -t -i is not present without tty", marks=skip_if_no_container)
        ,
        pytest.param(
            ["--env", "a=b", "--env", "test=success", "--name", "foobar"],
            r"--env a=b --env test=success", None, None, True, None,
            id="check --env", marks=skip_if_no_container,
        ),
        pytest.param(
            ["--oci-runtime", "foobar"], r"--runtime foobar", None, None, True, None,
            id="check --oci-runtime", marks=skip_if_no_container)
        ,
        pytest.param(
            ["--net", "bridge", "--name", "foobar"], r".*--network bridge",
            None, {"RAMALAMA_CONFIG": "NUL" if platform.system() == "Windows" else '/dev/null'}, True, None,
            id="check --net=bridge with RAMALAMA_CONFIG=/dev/null", marks=skip_if_no_container,
        ),
        pytest.param(
            ["--name", "foobar"], f".*{TEST_MODEL_FULL_NAME}.*",
            None, {"RAMALAMA_CONFIG": "NUL" if platform.system() == "Windows" else '/dev/null'}, True, None,
            id="check test_model with RAMALAMA_CONFIG=/dev/null", marks=skip_if_no_container,
        ),
        pytest.param(
            ["-c", "4096", "--name", "foobar"], r".*--ctx-size 4096",
            None, {"RAMALAMA_CONFIG": "NUL" if platform.system() == "Windows" else '/dev/null'}, True, None,
            id="check --ctx-size 4096 with RAMALAMA_CONFIG=/dev/null",  marks=skip_if_no_container,
        ),
        pytest.param(
            ["--cache-reuse", "512", "--name", "foobar"], r".*--cache-reuse 512", None,
            {"RAMALAMA_CONFIG": "NUL" if platform.system() == "Windows" else '/dev/null'}, True, None,
            id="check --cache-reuse with RAMALAMA_CONFIG=/dev/null", marks=skip_if_no_container,
        ),
        pytest.param(
            ["--name", "foobar"], r".*--temp 0.8", None, {
                "RAMALAMA_CONFIG": "NUL" if platform.system() == "Windows" else '/dev/null'
            }, True, None,
            id="check --temp default value is 0.8 with RAMALAMA_CONFIG=/dev/null", marks=skip_if_no_container,
        ),
        pytest.param(
            ["--seed", "9876", "--name", "foobar"], r".*--seed 9876",
            None, {"RAMALAMA_CONFIG": "NUL" if platform.system() == "Windows" else '/dev/null'}, True, None,
            id="check --seed 9876 with RAMALAMA_CONFIG=/dev/null", marks=skip_if_no_container,
        ),
        pytest.param(
            ["--name", "foobar"], r".*--pull newer", None,
            {"RAMALAMA_CONFIG": "NUL" if platform.system() == "Windows" else '/dev/null'}, True, None,
            id="check pull policy with RAMALAMA_CONFIG=/dev/null", marks=[skip_if_no_container, skip_if_docker],
        ),
        pytest.param(
            [], DEFAULT_PULL_PATTERN, None, None, True, None,
            id="check default pull policy",
            marks=[skip_if_no_container],
        ),
        pytest.param(
            ["--pull", "never", "-c", "4096", "--name", "foobbar"], r".*--pull never", None, None, True, None,
            id="check never pull policy", marks=skip_if_no_container,
        ),
        pytest.param(
            [], r".*--pull never", CONFIG_WITH_PULL_NEVER, None, True, None,
            id="check pull policy with RAMALAMA_CONFIG", marks=skip_if_no_container
        ),
        pytest.param(
            ["--name", "foobar"], r".*--name foobar", None, None, True, None,
            id="check --name foobar", marks=skip_if_no_container
        ),
        pytest.param(
            ["--name", "foobar"], r".*--cap-drop=all", None, None, True, None,
            id="check if --cap-drop=all is present", marks=skip_if_no_container
        ),
        pytest.param(
            ["--name", "foobar"], r".*no-new-privileges", None, None, True, None,
            id="check if --no-new-privs is present", marks=skip_if_no_container),
        pytest.param(
            ["--selinux", "True"], r".*--security-opt=label=disable", None, None, False, None,
            id="check --selinux=True enables container separation", marks=skip_if_no_container),
        pytest.param(
            ["--selinux", "False"], r".*--security-opt=label=disable", None, None, True, None,
            id="check --selinux=False disables container separation", marks=skip_if_no_container),
        pytest.param(
            ["--runtime-args", "--foo -bar"], r".*--foo\s+-bar", None, None, True, None,
            id="check --runtime-args", marks=skip_if_no_container
        ),
        pytest.param(
            ["--runtime-args", "--foo='a b c'"], r".*--foo=a b c", None, None, True, None,
            id="check --runtime-args=\"--foo='a b c'\"", marks=skip_if_no_container
        ),
        pytest.param(
            ["--privileged"], r".*--privileged", None, None, True, None,
            id="check --privileged", marks=skip_if_no_container
        ),
        pytest.param(
            ["--privileged"], r".*--cap-drop=all", None, None, False, None,
            id="check cap-drop=all is not set when --privileged", marks=skip_if_no_container
        ),
        pytest.param(
            ["--privileged"], r".*no-new-privileges", None, None, False, None,
            id="check no-new-privileges is not set when --privileged", marks=skip_if_no_container
        ),
        pytest.param(
            [], r".*foo:latest.*serve", None, {"RAMALAMA_IMAGE": "foo:latest"}, True, None,
            id="check run with RAMALAMA_IMAGE=foo:latest", marks=skip_if_no_container
        ),
        pytest.param(
            ["--ctx-size", "4096"], r".*serve.*--ctx-size 4096", None, None, True, None,
            id="check --ctx-size 4096", marks=skip_if_container,
        ),
        pytest.param(
            ["--ctx-size", "4096"], r".*--cache-reuse 256.*", None, None, True, None,
            id="check --cache-reuse is set by default to 256", marks=skip_if_container,
        ),
        pytest.param(
            [], r".*-e ASAHI_VISIBLE_DEVICES=99", None, {"ASAHI_VISIBLE_DEVICES": "99"}, True, None,
            id="check ASAHI_VISIBLE_DEVICES env var", marks=skip_if_no_container,
        ),
        pytest.param(
            [], r".*-e CUDA_LAUNCH_BLOCKING=1", None, {"CUDA_LAUNCH_BLOCKING": "1"}, True, None,
            id="check CUDA_LAUNCH_BLOCKING env var", marks=skip_if_no_container
        ),
        pytest.param(
            [], r".*-e HIP_VISIBLE_DEVICES=99", None, {"HIP_VISIBLE_DEVICES": "99"}, True, None,
            id="check HIP_VISIBLE_DEVICES env var", marks=skip_if_no_container
        ),
        pytest.param(
            [], r".*-e HSA_OVERRIDE_GFX_VERSION=0.0.0", None, {"HSA_OVERRIDE_GFX_VERSION": "0.0.0"}, True, None,
            id="check HSA_OVERRIDE_GFX_VERSION env var", marks=skip_if_no_container,
        ),
        pytest.param(
            [], r"(.*-e (HIP_VISIBLE_DEVICES=99|HSA_OVERRIDE_GFX_VERSION=0.0.0)){2}",
            None, {"HIP_VISIBLE_DEVICES": "99", "HSA_OVERRIDE_GFX_VERSION": "0.0.0"}, True, None,
            id="check HIP_VISIBLE_DEVICES & HSA_OVERRIDE_GFX_VERSION env vars", marks=skip_if_no_container,
        ),
        pytest.param(
            [
                "--device", "NUL" if platform.system() == "Windows" else '/dev/null',
                "--pull", "never"
            ],
            r".*--device (NUL|/dev/null) .*", None, None, True, None,
            id="check --device=/dev/null", marks=skip_if_no_container),
        pytest.param(
            ["--device", "none", "--pull", "never"], r".*--device.*", None, None, False, None,
            id="check --device with unsupported value", marks=skip_if_no_container),
    ],
)
# fmt: on
def test_params(extra_params, pattern, config, env_vars, expected, stdin):
    with RamalamaExecWorkspace(config=config, env_vars=env_vars) as ctx:
        result = ctx.check_output(RAMALAMA_DRY_RUN + extra_params + [TEST_MODEL], stdin=stdin)
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
            id="raise closing quotation error with --runtime-args", marks=skip_if_no_container,
        ),
        pytest.param(
            ["--selinux", "100"], r".*Error: Cannot coerce '100' to bool", None, None, 22, True,
            id="raise error when --selinux has non boolean value", marks=skip_if_no_container,
        ),
        pytest.param(
            ["--name", "foobar"],
            r"Error: --nocontainer and --name options conflict. The --name option requires a container.",
            None, None, 22, True,
            id="raise error on conflict between nocontainer and --name", marks=skip_if_container,
        ),
        pytest.param(
            ["--privileged"],
            r"Error: --nocontainer and --privileged options conflict. The --privileged option requires a container.",
            None, None, 22, True,
            id="raise error on conflict between nocontainer and --privileged", marks=skip_if_container,
        ),
    ],
)
# fmt: on
def test_params_errors(extra_params, pattern, config, env_vars, expected_exit_code, expected):
    with RamalamaExecWorkspace(config=config, env_vars=env_vars) as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(RAMALAMA_DRY_RUN + extra_params + [TEST_MODEL], stderr=STDOUT)
        assert exc_info.value.returncode == expected_exit_code
        assert bool(re.search(pattern, exc_info.value.output.decode("utf-8"))) is expected


@pytest.mark.e2e
def test_run_model_with_prompt(shared_ctx_with_models, test_model):
    import platform

    ctx = shared_ctx_with_models

    run_cmd = ["ramalama", "run", "--temp", "0"]
    if platform.system() in ["Darwin", "Windows"]:
        # FIXME: continues rambling on Windows and macOS without --max-token
        run_cmd.extend(["--max-tokens", "100"])

    run_cmd.extend([test_model, "Who is the primary writer of the declaration of independence?"])
    ctx.check_call(run_cmd)


_file_uri_id_suffix = 'C:/dir/file' if platform.system() == "Windows" else '/absolute_dir/file'
_file_uri_id_relative = "relative_dir/file"


@pytest.mark.e2e
@pytest.mark.parametrize(
    "scheme,relative_path",
    [
        pytest.param("file:", True, id=f"file:{_file_uri_id_relative}"),
        pytest.param("file:", False, id=f"file:{_file_uri_id_suffix}"),
        pytest.param("file:/", False, id=f"file:/{_file_uri_id_suffix}", marks=skip_if_not_windows),
        pytest.param("file://", False, id=f"file://{_file_uri_id_suffix}"),
    ],
)
def test_run_with_file_uri(shared_ctx_with_models, test_model, scheme, relative_path):
    ctx = shared_ctx_with_models

    model_info = json.loads(ctx.check_output(["ramalama", "inspect", test_model, "--json"]))
    model_path = Path(ctx.workspace_dir) / "test_model.gguf"
    shutil.copy(model_info["Path"], str(model_path))
    if relative_path:
        model_path = model_path.relative_to(ctx.workspace_dir)
    file_uri = f"{scheme}{model_path.as_posix()}"
    ctx.check_call(["ramalama", "run", file_uri], stdin=DEVNULL)

    if not relative_path:
        # Remove the original file, should still work with the model store URI
        model_path.unlink()
        ctx.check_call(["ramalama", "run", file_uri], stdin=DEVNULL)


@pytest.mark.e2e
@skip_if_not_windows
def test_run_with_unc_file_uri(shared_ctx_with_models, test_model):
    ctx = shared_ctx_with_models

    model_info = json.loads(ctx.check_output(["ramalama", "inspect", test_model, "--json"]))
    model_path = Path(WSL_TMP_DIR) / "test_model.gguf"
    shutil.copy(model_info["Path"], str(model_path))
    file_uri = model_path.as_uri()
    ctx.check_call(["ramalama", "run", file_uri], stdin=DEVNULL)


@pytest.mark.e2e
def test_run_keepalive(shared_ctx_with_models, test_model):
    ctx = shared_ctx_with_models
    ctx.check_call(["ramalama", "run", "--keepalive", "1s", test_model], stdin=DEVNULL)


@pytest.mark.e2e
@skip_if_no_container
@skip_if_docker
@skip_if_gh_actions_darwin
@pytest.mark.parametrize(
    "run_args, exit_code, error_pattern",
    [
        pytest.param(
            ["--image", "bogus", "--pull", "never", "tiny"],
            22,
            r".*Error: bogus: image not known",
            id="non-existing-image",
        ),
        pytest.param(
            [
                "--image",
                "bogus1",
                "--rag",
                "quay.io/ramalama/testrag",
                "--pull",
                "never",
                "tiny",
            ],
            22,
            r".*Error: quay.io/ramalama/testrag does not exist",
            id="non-existing-image-with-rag",
        ),
    ],
)
def test_run_with_non_existing_images_new(shared_ctx_with_models, run_args, exit_code, error_pattern):
    ctx = shared_ctx_with_models
    with pytest.raises(CalledProcessError) as exc_info:
        ctx.check_output(["ramalama", "run"] + run_args, stderr=STDOUT)
    assert exc_info.value.returncode == exit_code
    assert re.search(error_pattern, exc_info.value.output.decode("utf-8"))


@pytest.mark.e2e
@skip_if_no_container
@skip_if_darwin
@skip_if_docker
def test_run_with_rag():
    with RamalamaExecWorkspace() as ctx:
        result_a = ctx.check_output(RAMALAMA_DRY_RUN + ["--rag", "quay.io/ramalama/rag", "--pull", "never", "tiny"])
        assert re.search(r".*quay.io/.*-rag(@sha256)?:", result_a)

        result_b = ctx.check_output(
            RAMALAMA_DRY_RUN
            + ["--image", "quay.io/ramalama/ramalama:1.0", "--rag", "quay.io/ramalama/rag", "--pull", "never", "tiny"]
        )
        assert re.search(r".*quay.io/ramalama/ramalama:1.0", result_b)

        result_c = ctx.check_output(["ramalama", "--debug", "--dryrun", "run", "--rag", "quay.io/ramalama/rag", "tiny"])
        assert re.search(r".*rag_framework --debug serve", result_c)
