import random
import re
from pathlib import Path
from subprocess import STDOUT, CalledProcessError

import pytest

from test.e2e.utils import RamalamaExecWorkspace, check_output


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


@pytest.mark.e2e
def test_delete_snapshot_with_multiple_references():
    with RamalamaExecWorkspace() as ctx:
        initial_inventory = set([x for x in Path(ctx.storage_dir).rglob('*') if x.is_file()])
        ctx.check_call(["ramalama", "--store", ctx.storage_dir, "pull", "hf://ggml-org/SmolVLM-256M-Instruct-GGUF"])
        inventory_a = set([x for x in Path(ctx.storage_dir).rglob('*') if x.is_file()])
        ctx.check_call(
            ["ramalama", "--store", ctx.storage_dir, "pull", "hf://ggml-org/SmolVLM-256M-Instruct-GGUF:Q8_0"]
        )
        inventory_b = set([x for x in Path(ctx.storage_dir).rglob('*') if x.is_file()])
        ctx.check_call(["ramalama", "--store", ctx.storage_dir, "rm", "hf://ggml-org/SmolVLM-256M-Instruct-GGUF:Q8_0"])
        inventory_c = set([x for x in Path(ctx.storage_dir).rglob('*') if x.is_file()])
        ctx.check_call(["ramalama", "--store", ctx.storage_dir, "rm", "hf://ggml-org/SmolVLM-256M-Instruct-GGUF"])
        final_inventory = set([x for x in Path(ctx.storage_dir).rglob('*') if x.is_file()])
        assert final_inventory == initial_inventory
        assert inventory_c == inventory_a
        assert inventory_b != inventory_a
