import re

import pytest

from test.conftest import skip_if_no_llama_bench
from test.e2e.utils import check_output


@pytest.mark.e2e
@skip_if_no_llama_bench
def test_model_and_params_columns(test_model):
    result = check_output(["ramalama", "bench", "-t", "2", test_model])

    assert re.search(r"\|\s+model\s+\|\s+params", result)
