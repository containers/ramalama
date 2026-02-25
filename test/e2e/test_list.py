import json
import re
from datetime import datetime

import pytest

from test.e2e.utils import RamalamaExecWorkspace

HEADING_REGEX = "NAME *MODIFIED *SIZE"

TEST_IMAGE = "ollama://smollm:135m"


@pytest.fixture(scope="module")
def shared_ctx():
    """Provides an isolated and shared context for all tests in the module.
    Creates a ramalama workspace with configuration and pulls test image."""

    config = """
    [ramalama]
    store="{workspace_dir}/.local/share/ramalama"
    """
    with RamalamaExecWorkspace(config=config) as ctx:
        ctx.check_call(["ramalama", "-q", "pull", TEST_IMAGE])
        yield ctx


@pytest.mark.e2e
@pytest.mark.parametrize(
    "args,expected",
    [
        (["list"], True),
        (["list", "--noheading"], False),
        (["list", "-n"], False),
        (["--quiet", "list"], False),
        (["-q", "list"], False),
    ],
    ids=[
        "ramalama list",
        "ramalama list --noheading",
        "ramalama list -n",
        "ramalama --quiet list",
        "ramalama -q list",
    ],
)
def test_output(shared_ctx, args, expected):
    result = shared_ctx.check_output(["ramalama"] + args)
    assert bool(re.search(HEADING_REGEX, result)) is expected


@pytest.mark.e2e
def test_json_output(shared_ctx):
    json_raw = shared_ctx.check_output(["ramalama", "list", "--json"])
    result = json.loads(json_raw)

    for image_data in result:
        assert re.search(r"[\w:/]+", image_data["name"])
        assert image_data["size"] > 0
        assert datetime.fromisoformat(image_data["modified"])


@pytest.mark.e2e
def test_all_images_removed(shared_ctx):
    shared_ctx.check_call(["ramalama", "rm", "-a"])
    result = shared_ctx.check_output(["ramalama", "list", "--noheading"])
    assert result == ""
