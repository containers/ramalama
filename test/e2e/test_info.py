import json
import os
from test.conftest import skip_if_gh_actions_darwin
from test.e2e.utils import check_output

import pytest


@pytest.mark.e2e
@pytest.mark.distro_integration
@skip_if_gh_actions_darwin
def test_info(container_engine):
    info = json.loads(check_output(["ramalama", "info"]))
    version = check_output(["ramalama", "version"]).split()[2]

    assert info["Image"].startswith("quay.io/ramalama/ramalama")
    assert info["Runtime"] == "llama.cpp"
    assert info["Version"] == version
    assert info["Store"] in [f"{os.environ['HOME']}/.local/share/ramalama", "/var/lib/ramalama"]
    assert info["Engine"]["Name"] == container_engine


@pytest.mark.e2e
@pytest.mark.distro_integration
@skip_if_gh_actions_darwin
@pytest.mark.parametrize(
    "params, key, expected_value",
    [
        pytest.param(["--store", "/tmp/test_store"], "Store", "/tmp/test_store", id="with --store"),
        pytest.param(["--runtime", "vllm"], "Runtime", "vllm", id="with --runtime"),
        pytest.param(
            ["--image", "quay.io/testing/test:latest"], "Image", "quay.io/testing/test:latest", id="with --image"
        ),
    ],
)
def test_info_with_params(params, key, expected_value):
    info = json.loads(check_output(["ramalama"] + params + ["info"]))
    assert info[key] == expected_value
