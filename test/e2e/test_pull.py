import json
import random
import re
import string
from pathlib import Path
from subprocess import STDOUT, CalledProcessError
from test.conftest import skip_if_docker, skip_if_no_container, skip_if_no_huggingface_cli
from test.e2e.utils import RamalamaExecWorkspace

import pytest

TEST_MODEL = "smollm:135m"


@pytest.mark.e2e
@pytest.mark.distro_integration
def test_pull_no_model():
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(["ramalama", "pull"], stderr=STDOUT)
        assert exc_info.value.returncode == 2
        assert re.search(
            r".*ramalama pull: error: the following arguments are required: MODEL",
            exc_info.value.output.decode("utf-8"),
        )


@pytest.mark.e2e
@pytest.mark.distro_integration
@pytest.mark.parametrize(
    "model, env_vars, expected",
    [
        # fmt: off
        pytest.param(
            "smollm:135m", {"RAMALAMA_TRANSPORT": "ollama"}, "ollama://smollm/smollm:135m",
            id="smollm:135m model with RAMALAMA_TRANSPORT=ollama"
        ),
        pytest.param(
            "ollama://smollm:135m", None, "ollama://smollm/smollm:135m",
            id="smollm:135m model with ollama:// url"
        ),
        pytest.param(
            "https://ollama.com/library/smollm:135m", None, "https://ollama.com/library/smollm:135m",
            id="smollm:135m model with http url from ollama"
        ),
        pytest.param(
            "Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf",
            {"RAMALAMA_TRANSPORT": "huggingface"},
            "hf://Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf",
            id="smollm-360M-instruct-add-basics.IQ2_XXS.gguf model with RAMALAMA_TRANSPORT=huggingface"
        ),
        pytest.param(
            "hf://Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf",
            None, "hf://Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf",
            id="smollm-360M-instruct-add-basics.IQ2_XXS.gguf model with hf:// url"
        ),
        pytest.param(
            "huggingface://Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf",
            None, "hf://Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf",
            id="smollm-360M-instruct-add-basics.IQ2_XXS.gguf model with huggingface:// url"
        ),
        # FIXME: why these ones skip_if_no_huggingface_cli? huggingface-cli is by default in .[dev]
        pytest.param(
            "huggingface://TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            None, "hf://TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            id="TinyLlama-1.1B-Chat-v1.0 model with huggingface:// url"
        ),
        pytest.param(
            "hf://ggml-org/SmolVLM-256M-Instruct-GGUF",
            None, "hf://ggml-org/SmolVLM-256M-Instruct-GGUF",
            id="SmolVLM-256M-Instruct-GGUF model with hf:// url"
        ),
        pytest.param(
            "hf://ggml-org/SmolVLM-256M-Instruct-GGUF:Q8_0",
            None, "hf://ggml-org/SmolVLM-256M-Instruct-GGUF:Q8_0",
            id="SmolVLM-256M-Instruct-GGUF:Q8_0 model with hf:// url"
        ),
        pytest.param(
            "quay.io/ramalama/smollm:135m", {"RAMALAMA_TRANSPORT": "oci"}, "oci://quay.io/ramalama/smollm:135m",
            id="smollm:135m model with RAMALAMA_TRANSPORT=oci",
            marks=skip_if_no_container
        ),
        pytest.param(
            "oci://quay.io/ramalama/smollm:135m", None, "oci://quay.io/ramalama/smollm:135m",
            id="smollm:135m model with oci:// url",
            marks=skip_if_no_container
        ),
        pytest.param(
            "file://{workspace_dir}/mymodel.gguf", None, "file://{workspace_dir}/mymodel.gguf",
            id="{workspace_dir}/mymodel.gguf model with file:// url",
            marks=skip_if_no_container
        ),
        # fmt: on
    ],
)
def test_pull(model, env_vars, expected):
    with RamalamaExecWorkspace(env_vars=env_vars) as ctx:
        ramalama_cli = ["ramalama", "--store", ctx.storage_dir]

        # if the transport is file then ensure that the local model exists
        if model.startswith("file://"):
            model_path = Path(model.format(workspace_dir=ctx.workspace_dir).replace("file://", ""))
            model_path.parent.mkdir(parents=True, exist_ok=True)
            model_path.touch()

        # Pull image
        ctx.check_call(ramalama_cli + ["pull", model.format(workspace_dir=ctx.workspace_dir)])

        # Get ramalama list
        model_list = json.loads(ctx.check_output(ramalama_cli + ["list", "--json"]))

        # Check if the model pull is the expected
        assert model_list[0]["name"] == expected.format(workspace_dir=ctx.workspace_dir)


@pytest.mark.e2e
@pytest.mark.distro_integration
def test_pull_huggingface_tag_multiple_references():
    with RamalamaExecWorkspace() as ctx:
        ramalama_cli = ["ramalama", "--store", ctx.storage_dir]
        model_url_list = ["hf://ggml-org/SmolVLM-256M-Instruct-GGUF", "hf://ggml-org/SmolVLM-256M-Instruct-GGUF:Q8_0"]

        for model_url in model_url_list:
            ctx.check_call(ramalama_cli + ["pull", model_url])

        model_list = json.loads(ctx.check_output(ramalama_cli + ["list", "--json"]))
        assert set(model_url_list).issubset([model["name"] for model in model_list])

        result = ctx.check_output(ramalama_cli + ["--debug", "rm", model_url_list[0]], stderr=STDOUT)
        assert re.search(r".*Not removing snapshot", result)

        result = ctx.check_output(ramalama_cli + ["--debug", "rm", model_url_list[1]], stderr=STDOUT)
        assert re.search(r".*Snapshot removed", result)


@pytest.mark.e2e
@pytest.mark.distro_integration
def test_pull_using_ollama_cache():
    # FIXME: review with the maintainers if still makes sense
    pass


@pytest.mark.e2e
@pytest.mark.distro_integration
@skip_if_no_huggingface_cli
def test_pull_using_huggingface_cache():
    # FIXME: review with the maintainers if still makes sense
    pass


@pytest.mark.e2e
@pytest.mark.distro_integration
@skip_if_no_container
@skip_if_docker
def test_pull_with_registry(container_registry):
    # FIXME: Check with the maintainers if some of the original tests with registry are necessary
    with RamalamaExecWorkspace() as ctx:
        ramalama_cli = ["ramalama", "--store", ctx.storage_dir]
        authfile = (Path(ctx.workspace_dir) / "authfile.json").as_posix()
        auth_flags = ["--authfile", authfile, "--tls-verify", "false"]
        credential_flags = ["--username", container_registry.username, "--password", container_registry.password]

        # Login to the container registry with ramalama
        ctx.check_call(["ramalama", "login"] + auth_flags + credential_flags + [container_registry.url])

        # Create fake model
        fake_model = Path(ctx.workspace_dir) / "fake-model"
        fake_model_local_url = f"file://{fake_model.as_posix()}"
        fake_model_registry_url = f"{container_registry.url}/fake-model-raw:latest"
        with fake_model.open("w") as f:
            f.write(''.join(random.choices(string.ascii_letters + string.digits, k=30)))

        # Push fake model
        ctx.check_call(ramalama_cli + ["push"] + auth_flags + [fake_model_local_url, fake_model_registry_url])

        # Pull fake model
        ctx.check_call(ramalama_cli + ["pull"] + auth_flags + [fake_model_registry_url])

        # Check if the fake model was pulled correctly
        model_list = json.loads(ctx.check_output(ramalama_cli + ["list", "--json"]))
        assert fake_model_registry_url in [model["name"] for model in model_list]

        # Clean fake image
        ctx.check_call(["podman", "rmi", fake_model_registry_url.replace("oci://", "")])
