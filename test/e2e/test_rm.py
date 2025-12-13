import random
import re
from subprocess import STDOUT, CalledProcessError
from test.e2e.utils import check_output

import pytest


@pytest.mark.e2e
def test_delete_non_existing_image():
    image_name = f"rm_random_image_{random.randint(0, 9999)}"
    with pytest.raises(CalledProcessError) as exc_info:
        check_output(["ramalama", "rm", image_name], stderr=STDOUT)

    assert exc_info.value.returncode == 22
    assert re.match(
        f"Error: Model '{image_name}' not found",
        exc_info.value.output.decode("utf-8"),
    )


@pytest.mark.e2e
def test_delete_non_existing_image_with_ignore_flag():
    image_name = f"rm_random_image_{random.randint(0, 9999)}"
    result = check_output(["ramalama", "rm", "--ignore", image_name])
    assert result == ""
