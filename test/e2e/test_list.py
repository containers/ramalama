import json
import re
from datetime import datetime
from test.e2e.utils import check_call, check_output

import pytest

HEADING_REGEX = "NAME *MODIFIED *SIZE"


@pytest.fixture(scope="module")
def pull_smollm():
    yield check_call(["ramalama", "-q", "pull", "ollama://smollm:135m"])


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
        "ramalama --quite list",
        "ramalama -q list",
    ],
)
def test_output(pull_smollm, args, expected):
    result = check_output(["ramalama"] + args)

    assert bool(re.search(HEADING_REGEX, result)) is expected


@pytest.mark.e2e
def test_json_output(pull_smollm):
    json_raw = check_output(["ramalama", "list", "--json"])
    result = json.loads(json_raw)

    for image_data in result:
        assert re.search(r"[\w\d:/]+", image_data["name"])
        assert image_data["size"] > 0
        assert datetime.fromisoformat(image_data["modified"])
