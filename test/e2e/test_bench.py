import re
from test.conftest import skip_if_no_llama_bench
from test.e2e.utils import check_output

import pytest


@pytest.mark.e2e
@skip_if_no_llama_bench
def test_model_and_size_columns(test_model):
    result = check_output(["ramalama", "bench", "-t", "2", test_model])

    assert re.search(r"\|\s+model\s+\|\s+size", result)
