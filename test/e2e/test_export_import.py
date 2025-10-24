from test.e2e.utils import RamalamaExecWorkspace

import pytest


@pytest.mark.e2e
def test_export_import():

    old_store_path = "{workspace_dir}/.local/share/ramalama"
    new_store_path = "{workspace_dir}/.local/share/ramalama-new"

    with RamalamaExecWorkspace() as ctx:
        assert 0 == ctx.check_call(["ramalama", "--store", old_store_path, "pull", "smollm:135m"])
        assert "hf://HuggingFaceTB/smollm-135M-instruct-v0.2-Q8_0-GGUF" in ctx.check_output(
            ["ramalama", "--store", old_store_path, "ls"]
        )

        assert 0 == ctx.check_call(["ramalama", "--store", old_store_path, "export", "--output", "/var/tmp"])
        assert 0 == ctx.check_call(
            ["ramalama", "--store", new_store_path, "import", "--input", "/var/tmp/ramalama.tar.gz"]
        )
        assert "hf://HuggingFaceTB/smollm-135M-instruct-v0.2-Q8_0-GGUF" in ctx.check_output(
            ["ramalama", "--store", new_store_path, "ls"]
        )
