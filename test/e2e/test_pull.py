import json
import random
import re
import string
from pathlib import Path, PurePosixPath
from subprocess import STDOUT, CalledProcessError
from test.conftest import (
    skip_if_big_endian_machine,
    skip_if_darwin,
    skip_if_little_endian_machine,
    skip_if_no_container,
    skip_if_no_ollama,
)
from test.e2e.utils import RamalamaExecWorkspace
from time import time

import pytest

from ramalama.path_utils import normalize_host_path_for_container


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
def test_pull_non_existing_model():
    random_model_name = f"non_existing_model_{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(["ramalama", "pull", random_model_name], stderr=STDOUT)
        assert exc_info.value.returncode == 22
        assert re.search(
            fr".*Error: Manifest for {random_model_name}:latest was not found in the Ollama registry",
            exc_info.value.output.decode("utf-8"),
        )


@pytest.mark.e2e
@pytest.mark.distro_integration
@pytest.mark.parametrize(
    "model, env_vars, expected",
    [
        # fmt: off
        pytest.param(
            "ollama://tinyllama", None, "ollama://library/tinyllama:latest",
            id="tinyllama model with ollama:// url"
        ),
        pytest.param(
            "smollm:360m", {"RAMALAMA_TRANSPORT": "ollama"}, "ollama://library/smollm:360m",
            id="smollm:360m model with RAMALAMA_TRANSPORT=ollama"
        ),
        pytest.param(
            "ollama://smollm:360m", None, "ollama://library/smollm:360m",
            id="smollm:360m model with ollama:// url"
        ),
        pytest.param(
            "https://ollama.com/library/smollm:135m", None, "ollama://library/smollm:135m",
            id="smollm:135m model with http url from ollama"
        ),
        pytest.param(
            "hf://Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf",
            None,
            "hf://Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf",
            id="hf://Felladrin/../smollm-360M-instruct-add-basics.IQ2_XXS.gguf model"
        ),
        pytest.param(
            "huggingface://Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf",
            None,
            "hf://Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf",
            id="huggingface://Felladrin/../smollm-360M-instruct-add-basics.IQ2_XXS.gguf model"
        ),
        pytest.param(
            "Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf",
            {"RAMALAMA_TRANSPORT": "huggingface"},
            "hf://Felladrin/gguf-smollm-360M-instruct-add-basics/smollm-360M-instruct-add-basics.IQ2_XXS.gguf",
            id="Felladrin/../smollm-360M-instruct-add-basics.IQ2_XXS.gguf model with RAMALAMA_TRANSPORT=huggingface"
        ),
        pytest.param(
            "oci://quay.io/ramalama/smollm:135m", None, "oci://quay.io/ramalama/smollm:135m",
            id="smollm:135m model with oci:// url",
            marks=skip_if_no_container
        ),
        pytest.param(
            "quay.io/ramalama/smollm:135m", {"RAMALAMA_TRANSPORT": "oci"}, "oci://quay.io/ramalama/smollm:135m",
            id="smollm:135m model with RAMALAMA_TRANSPORT=oci",
            marks=skip_if_no_container
        ),
        pytest.param(
            Path("mymodel.gguf"), None, Path("mymodel.gguf"),
            id="{workspace_dir}/mymodel.gguf model with file:// url",
        )
        # fmt: on
    ],
)
def test_pull(model, env_vars, expected):
    with RamalamaExecWorkspace(env_vars=env_vars) as ctx:
        ramalama_cli = ["ramalama", "--store", str(ctx.storage_path)]

        # Resolve model_name depending on the type of model parameter
        if isinstance(model, str):
            model_name = model
        elif isinstance(model, Path):
            model_path = ctx.workspace_path / model
            model_path.parent.mkdir(parents=True, exist_ok=True)
            model_path.touch()
            model_name = "file://" + model_path.as_posix()
        else:
            raise ValueError(f"Unsupported model type: {type(model)}")

        # Resolve expected_name depending on the type of the expected parameter
        if isinstance(expected, str):
            expected_name = expected
        elif isinstance(expected, Path):
            expected_name = (
                "file://"
                + PurePosixPath(normalize_host_path_for_container(str(ctx.workspace_path)))
                .joinpath(PurePosixPath(expected))
                .as_posix()
            )
        else:
            raise ValueError(f"Unsupported expected type: {type(expected)}")

        # Pull image
        ctx.check_call(ramalama_cli + ["pull", model_name])

        # Get ramalama list
        model_list = json.loads(ctx.check_output(ramalama_cli + ["list", "--json", "--sort", "modified"]))

        # Clean pulled images
        ctx.check_call(ramalama_cli + ["rm", model_name])

        # Check if the model pull is the expected
        assert model_list[0]["name"] == expected_name


@pytest.mark.e2e
@pytest.mark.distro_integration
def test_pull_model_layers_download():
    with RamalamaExecWorkspace() as ctx:
        ramalama_cli = ["ramalama", "--store", str(ctx.storage_path)]
        output = ctx.check_output(
            ramalama_cli + ["pull", "hf://owalsh/SmolLM2-135M-Instruct-GGUF-Split:Q4_0"], stderr=STDOUT
        )

        for i in range(1, 4):
            assert f"Downloading Q4_0/SmolLM2-135M-Instruct-Q4_0-0000{i}-of-00003.gguf" in output


@pytest.mark.e2e
@pytest.mark.distro_integration
def test_pull_huggingface_tag_multiple_references():
    with RamalamaExecWorkspace() as ctx:
        ramalama_cli = ["ramalama", "--store", str(ctx.storage_path)]
        model_url_list = ["hf://ggml-org/SmolVLM-256M-Instruct-GGUF", "hf://ggml-org/SmolVLM-256M-Instruct-GGUF:Q8_0"]

        for model_url in model_url_list:
            ctx.check_call(ramalama_cli + ["pull", model_url])

        model_list = json.loads(ctx.check_output(ramalama_cli + ["list", "--json", "--sort", "modified"]))
        assert set(model_url_list).issubset([model["name"] for model in model_list])

        result = ctx.check_output(ramalama_cli + ["--debug", "rm", model_url_list[0]], stderr=STDOUT)
        assert re.search(r".*Not removing snapshot", result)

        result = ctx.check_output(ramalama_cli + ["--debug", "rm", model_url_list[1]], stderr=STDOUT)
        assert re.search(r".*Snapshot removed", result)


@pytest.mark.e2e
@pytest.mark.distro_integration
@pytest.mark.parametrize(
    "model, expected",
    [
        pytest.param(
            "tiny",
            "Endian mismatch of host (BIG) and model (LITTLE)",
            marks=[skip_if_little_endian_machine],
            id="le model on be machine",
        ),
        pytest.param(
            "stories-be:260k",
            "Endian mismatch of host (LITTLE) and model (BIG)",
            marks=[skip_if_big_endian_machine],
            id="be model on le machine",
        ),
    ],
)
def test_pull_wrong_endian_model_error(model, expected):
    with RamalamaExecWorkspace() as ctx:
        with pytest.raises(CalledProcessError) as exc_info:
            ctx.check_output(
                ["ramalama", "--store", str(ctx.storage_path), "pull", "--verify=on", model], stderr=STDOUT
            )
        assert exc_info.value.returncode == 1
        assert expected in exc_info.value.output.decode("utf-8")


@pytest.mark.e2e
@pytest.mark.distro_integration
@skip_if_no_ollama
@skip_if_darwin
@pytest.mark.parametrize(
    "ollama_model, model, env_vars, expected",
    [
        pytest.param(
            "tinyllama",
            "ollama://library/tinyllama",
            None,
            "ollama://library/tinyllama:latest",
            id="tinyllama model with ollama:// url",
        ),
        pytest.param(
            "smollm:135m",
            "https://ollama.com/library/smollm:135m",
            None,
            "ollama://library/smollm:135m",
            id="smollm:135m model with http url from ollama",
        ),
        pytest.param(
            "smollm:360m",
            "smollm:360m",
            {"RAMALAMA_TRANSPORT": "ollama"},
            "ollama://library/smollm:360m",
            id="smollm:360m model with RAMALAMA_TRANSPORT=ollama",
        ),
    ],
)
def test_pull_using_ollama_cache(ollama_server, ollama_model, model, env_vars, expected):
    with RamalamaExecWorkspace(env_vars=env_vars) as ctx:
        ramalama_cli = ["ramalama", "--store", str(ctx.storage_path)]

        # Ensure ollama cache exists and is set as environment variable
        ctx.environ["OLLAMA_HOST"] = ollama_server.url
        ctx.environ["OLLAMA_MODELS"] = str(ollama_server.models_dir)

        # Pull image using ollama server and ollama cli
        ollama_pull_start_time = time()
        ollama_server.pull_model(ollama_model)
        ollama_pull_end_time = time()
        ollama_pull_time = ollama_pull_end_time - ollama_pull_start_time

        # Pull image using ramalama cli
        ramalama_pull_start_time = time()
        ctx.check_call(ramalama_cli + ["pull", model])
        ramalama_pull_end_time = time()
        ramalama_pull_time = ramalama_pull_end_time - ramalama_pull_start_time

        # Check if the model pull is the expected
        model_list = json.loads(ctx.check_output(ramalama_cli + ["list", "--json", "--sort", "modified"]))
        assert model_list[0]["name"] == expected

        # Compare the ollama pull time with the ramalama cached pull time
        assert (ollama_pull_time / 2) > ramalama_pull_time


@pytest.mark.e2e
@pytest.mark.distro_integration
@skip_if_no_container
@pytest.mark.xfail("config.option.container_engine == 'docker'", reason="docker login does not support --tls-verify")
def test_pull_with_registry(container_registry, container_engine):
    with RamalamaExecWorkspace() as ctx:
        ramalama_cli = ["ramalama", "--store", str(ctx.storage_path)]
        authfile = str(ctx.workspace_path / "authfile.json")
        auth_flags = ["--authfile", authfile, "--tls-verify", "false"]
        credential_flags = ["--username", container_registry.username, "--password", container_registry.password]

        # Login to the container registry with ramalama
        ctx.check_call(["ramalama", "login"] + auth_flags + credential_flags + [container_registry.url])

        # Create fake model
        fake_model = ctx.workspace_path / "fake-model"
        fake_model_local_url = fake_model.as_uri()
        fake_model_registry_url = f"{container_registry.url}/fake-model-raw:latest"
        with fake_model.open("w") as f:
            f.write(''.join(random.choices(string.ascii_letters + string.digits, k=30)))

        # Push fake model
        ctx.check_call(ramalama_cli + ["push"] + auth_flags + [fake_model_local_url, fake_model_registry_url])

        # Pull fake model
        ctx.check_call(ramalama_cli + ["pull"] + auth_flags + [fake_model_registry_url])

        # Check if the fake model was pulled correctly
        model_list = json.loads(ctx.check_output(ramalama_cli + ["list", "--json"]))
        assert fake_model_registry_url in [x["name"] for x in model_list]

        # Clean fake image
        ctx.check_call([container_engine, "rmi", fake_model_registry_url.replace("oci://", "")])

        # Clean dangling images
        ctx.check_call([container_engine, "image", "prune", "-f"])
