import re
from test.e2e.utils import check_output

import pytest


@pytest.mark.e2e
def test_version_line_output():
    result = check_output(["ramalama", "version"])

    assert re.match(r"ramalama version \d+\.\d+.\d+", result)
