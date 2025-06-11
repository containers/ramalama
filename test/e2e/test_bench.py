import re
from test.conftest import skip_if_no_container
from test.e2e.utils import check_output

import pytest


@pytest.mark.e2e
@skip_if_no_container
def test_model_and_size_columns():
    result = check_output(["ramalama", "bench", "-t", "2", "smollm:135m"])

    assert re.match(r".*model.*size.*", result)
