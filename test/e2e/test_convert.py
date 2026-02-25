import json
import re
from pathlib import Path
from subprocess import STDOUT, CalledProcessError

import pytest

from test.conftest import (
    skip_if_container,
    skip_if_docker,
    skip_if_no_container,
    skip_if_ppc64le,
    skip_if_s390x,
)
from test.e2e.utils import RamalamaExecWorkspace


@pytest.mark.e2e
def test_convert_custom_gguf_config():
    config = """
    [ramalama]
    gguf_quantization_mode="Q5_0"
    """

    with RamalamaExecWorkspace(config=config) as ctx:
        result = ctx.check_output(["ramalama", "convert", "--help"])
        assert re.search("GGUF quantization format. If specified without value, Q5_0 is used", result)


# fmt: off
@pytest.mark.e2e
@skip_if_docker
@skip_if_no_container
@skip_if_ppc64le
@skip_if_s390x
@pytest.mark.parametrize(
    "in_model, out_model, extra_params, expected",
    [
        pytest.param(
            Path("aimodel"), "foobar", None,
            "oci://localhost/foobar:latest",
            id="{workspace_uri}/aimodel -> foobar",
        ),
        pytest.param(
            Path("aimodel"), "oci://foobar", None,
            "oci://localhost/foobar:latest",
            id="{workspace_uri}/aimodel -> oci://foobar",
        ),
        pytest.param(
            "tiny", "oci://quay.io/ramalama/tiny", None,
            "oci://quay.io/ramalama/tiny:latest",
            id="tiny -> oci://quay.io/ramalama/tiny",
        ),
        pytest.param(
            "ollama://tinyllama", "oci://quay.io/ramalama/tinyllama", None,
            "oci://quay.io/ramalama/tinyllama:latest",
            id="ollama://tinyllama -> oci://quay.io/ramalama/tinyllama",
        ),
        pytest.param(
            "hf://TinyLlama/TinyLlama-1.1B-Chat-v1.0", "oci://quay.io/ramalama/tinyllama", None,
            "oci://quay.io/ramalama/tinyllama:latest",
            id="hf://TinyLlama/TinyLlama-1.1B-Chat-v1.0 -> oci://quay.io/ramalama/tinyllama",
        ),
        pytest.param(
            "hf://TinyLlama/TinyLlama-1.1B-Chat-v1.0", "oci://quay.io/ramalama/tiny-q4-0",
            ["--gguf", "Q4_0"],
            "oci://quay.io/ramalama/tiny-q4-0:latest",
            id="hf://TinyLlama/TinyLlama-1.1B-Chat-v1.0 -> oci://quay.io/ramalama/tiny-q4-0 (--gguf Q4_0)",
        ),
    ],
)
# fmt: on
def test_convert(in_model, out_model, extra_params, expected):
    with RamalamaExecWorkspace() as ctx:
        ramalama_cli = ["ramalama", "--store", ctx.storage_dir]

        # Ensure a local model exists if it is provided
        if isinstance(in_model, Path):
            in_model_path = Path(ctx.workspace_dir) / in_model
            in_model_path.parent.mkdir(parents=True, exist_ok=True)
            with in_model_path.open("w") as f:
                f.write("hello ai model!")
            in_model = in_model_path.as_uri()

        # Exec convert
        ramalama_convert_cli = ramalama_cli + ["convert"]
        if extra_params:
            ramalama_convert_cli += extra_params

        try:
            ctx.check_call(ramalama_convert_cli + [in_model, out_model])

            # Get ramalama list
            model_list = json.loads(ctx.check_output(ramalama_cli + ["list", "--json"]))

            # Check if the model pull is the expected
            model_name_list = [model["name"] for model in model_list]
            assert expected in model_name_list
        finally:
            # Clean images
            ctx.check_call(ramalama_cli + ["rm", "--ignore", expected.replace("oci://", "")])


# fmt: off
@pytest.mark.e2e
@pytest.mark.parametrize(
    "in_model, out_model, expected_exit_code, expected",
    [
        pytest.param(
            None, None, 2, ".*ramalama convert: error: the following arguments are required: SOURCE, TARGET",
            id="raise error if no models",
            marks=[skip_if_no_container]
        ),
        pytest.param(
            "tiny", None, 2, ".*ramalama convert: error: the following arguments are required: TARGET",
            id="raise error if target model is missing",
            marks=[skip_if_no_container]
        ),
        pytest.param(
            "bogus", "foobar", 22, ".*Error: Manifest for bogus:latest was not found in the Ollama registry",
            id="raise error if model doesn't exist",
            marks=[skip_if_no_container]
        ),
        pytest.param(
            "oci://quay.io/ramalama/smollm:135m", "oci://foobar", 22,
            "Error: converting from an OCI based image oci://quay.io/ramalama/smollm:135m is not supported",
            id="raise error when models are oci (not supported)",
            marks=[skip_if_no_container]
        ),
        pytest.param(
            "file://{workspace_dir}/aimodel", "ollama://foobar", 22,
            "Error: ollama://foobar invalid: Only OCI Model types supported",
            id="raise error when target model is ollama and source mode is not OCI",
            marks=[skip_if_no_container]
        ),
        pytest.param(
            "tiny", "quay.io/ramalama/foobar", 22,
            "Error: convert command cannot be run with the --nocontainer option.",
            id="raise error when --nocontainer flag",
            marks=[skip_if_container]
        ),
    ],
)
# fmt: on
def test_convert_errors(in_model, out_model, expected_exit_code, expected):
    with RamalamaExecWorkspace() as ctx:
        # Ensure a local model exists if it is provided
        if in_model and in_model.startswith("file://"):
            in_model = in_model.format(workspace_dir=ctx.workspace_dir)
            in_model_path = Path(in_model.replace("file://", ""))
            in_model_path.parent.mkdir(parents=True, exist_ok=True)
            with in_model_path.open("w") as f:
                f.write("hello ai model!")

        ramalama_convert_cli = ["ramalama", "convert", in_model, out_model]

        # Clean Nones if models are missing
        ramalama_convert_cli = list(filter(None, ramalama_convert_cli))

        # Exec ramalama convert
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(ramalama_convert_cli, stderr=STDOUT)

        # Check the expected results
        assert exc_info.value.returncode == expected_exit_code
        assert re.search(expected, exc_info.value.output.decode("utf-8"))
