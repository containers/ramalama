import json
import tempfile
from pathlib import Path

import pytest

from ramalama.version import version
from test.conftest import skip_if_gh_actions_darwin
from test.e2e.utils import RamalamaExecWorkspace, check_output


@pytest.mark.e2e
@pytest.mark.distro_integration
@skip_if_gh_actions_darwin
def test_info(monkeypatch, container_engine):
    monkeypatch.delenv("RAMALAMA_DEFAULT_IMAGE", raising=False)
    monkeypatch.delenv("RAMALAMA_IMAGES", raising=False)
    info = json.loads(check_output(["ramalama", "info"]))

    assert info["Image"].startswith("quay.io/ramalama/")
    assert info["Version"] == version()
    assert info["Store"] in [str(Path.home() / ".local" / "share" / "ramalama"), "/var/lib/ramalama"]
    assert info["Engine"]["Name"] == container_engine


@pytest.mark.e2e
@pytest.mark.distro_integration
@skip_if_gh_actions_darwin
@pytest.mark.parametrize(
    "params, key, expected_value",
    [
        pytest.param(
            ["--store", str(Path(tempfile.gettempdir()) / "test_store")],
            ["Store"],
            str(Path(tempfile.gettempdir()) / "test_store"),
            id="with --store",
        ),
        pytest.param(["--runtime", "vllm"], ["Inference", "Default"], "vllm", id="with --runtime"),
    ],
)
def test_info_with_params(params, key, expected_value):
    info = json.loads(check_output(["ramalama"] + params + ["info"]))
    value = info
    for k in key:
        value = value[k]
    assert value == str(expected_value)


@pytest.mark.e2e
@pytest.mark.distro_integration
@skip_if_gh_actions_darwin
def test_info_selinux_state():
    # Verify selinux defaults to disabled
    info_default = json.loads(check_output(["ramalama", "info"]))
    assert info_default["Selinux"] is False

    # Verify selinux setting from ramalama.conf
    config = """
    [ramalama]
    selinux=True
    """
    with RamalamaExecWorkspace(config=config) as ctx:
        info = json.loads(ctx.check_output(["ramalama", "info"]))
        assert info["Selinux"] is True
