import re

import pytest
from utils import check_output


@pytest.mark.e2e
def test_version_line_output():
    result = check_output(["ramalama", "version"])

    assert re.match(r"ramalama version \d+\.\d+.\d+", result)


@pytest.mark.e2e
def test_version_flag():
    result = check_output(["ramalama", "--version"])

    assert re.match(r"ramalama version \d+\.\d+.\d+", result)


@pytest.mark.e2e
def test_version_flag_short():
    result = check_output(["ramalama", "-v"])

    assert re.match(r"ramalama version \d+\.\d+.\d+", result)


@pytest.mark.e2e
def test_version_flag_matches_subcommand():
    flag_result = check_output(["ramalama", "--version"])
    subcmd_result = check_output(["ramalama", "version"])

    assert flag_result == subcmd_result
