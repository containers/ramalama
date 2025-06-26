import os
import shutil
import tempfile
from contextlib import ExitStack
from pathlib import Path
from sys import platform
from unittest.mock import patch

import pytest

from ramalama.cli import configure_subcommands, create_argument_parser
from ramalama.common import accel_image, get_accel, rm_until_substring, verify_checksum
from ramalama.config import DEFAULT_IMAGE, default_config


@pytest.mark.parametrize(
    "input,rm_until,expected",
    [
        ("", "", ""),
        ("huggingface://granite-code", "://", "granite-code"),
        ("hf://granite-code", "://", "granite-code"),
        ("hf.co/granite-code", "hf.co/", "granite-code"),
        (
            "http://huggingface.co/ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf",
            ".co/",
            "ibm-granite/granite-3b-code-base-2k-GGUF/blob/main/granite-3b-code-base.Q4_K_M.gguf",
        ),
        ("modelscope://granite-code", "://", "granite-code"),
        ("ms://granite-code", "://", "granite-code"),
        (
            "file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf",
            "",
            "file:///tmp/models/granite-3b-code-base.Q4_K_M.gguf",
        ),
    ],
)
def test_rm_until_substring(input: str, rm_until: str, expected: str):
    actual = rm_until_substring(input, rm_until)
    assert actual == expected


valid_input = """{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ if .Prompt }}<|im_start|>user
{{ .Prompt }}<|im_end|>
{{ end }}<|im_start|>assistant
{{ .Response }}<|im_end|>
"""

tampered_input = """{"model_format":"gguf","model_family":"llama","model_families":["llama"],"model_type":"361.82M","file_type":"Q4_0","architecture":"amd64","os":"linux","rootfs":{"type":"layers","diff_ids":["sha256:f7ae49f9d598730afa2de96fc7dade47f5850446bf813df2e9d739cc8a6c4f29","sha256:62fbfd9ed093d6e5ac83190c86eec5369317919f4b149598d2dbb38900e9faef","sha256:cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30","sha256:ca7a9654b5469dc2d638456f31a51a03367987c54135c089165752d9eeb08cd7"]}}

I have been tampered with

"""  # noqa: E501


@pytest.mark.parametrize(
    "input_file_name,content,expected_error,expected_result",
    [
        ("invalidname", "", ValueError, None),
        ("sha256:123", "RamaLama - make working with AI boring through the use of OCI containers.", ValueError, None),
        ("sha256:62fbfd9ed093d6e5ac83190c86eec5369317919f4b149598d2dbb38900e9faef", valid_input, None, True),
        ("sha256-62fbfd9ed093d6e5ac83190c86eec5369317919f4b149598d2dbb38900e9faef", valid_input, None, True),
        ("sha256:16cd1aa2bd52b0e87ff143e8a8a7bb6fcb0163c624396ca58e7f75ec99ef081f", tampered_input, None, False),
    ],
)
def test_verify_checksum(input_file_name: str, content: str, expected_error: Exception, expected_result: bool):
    # skip this test case on Windows since colon is not a valid file symbol
    if ":" in input_file_name and platform == "win32":
        return

    full_dir_path = os.path.join(Path(__file__).parent, "verify_checksum")
    file_path = os.path.join(full_dir_path, input_file_name)

    try:
        os.makedirs(full_dir_path, exist_ok=True)
        with open(file_path, "w") as f:
            f.write(content)

        if expected_error is None:
            assert verify_checksum(file_path) == expected_result
            return

        with pytest.raises(expected_error):
            verify_checksum(file_path)
    finally:
        shutil.rmtree(full_dir_path)


DEFAULT_IMAGES = {
    "HIP_VISIBLE_DEVICES": "quay.io/ramalama/rocm",
}


@pytest.mark.parametrize(
    "accel_env,env_override,config_override,expected_result",
    [
        (None, None, None, f"{DEFAULT_IMAGE}:latest"),
        (None, f"{DEFAULT_IMAGE}:latest", None, f"{DEFAULT_IMAGE}:latest"),
        (None, None, f"{DEFAULT_IMAGE}:latest", f"{DEFAULT_IMAGE}:latest"),
        ("HIP_VISIBLE_DEVICES", None, None, "quay.io/ramalama/rocm:latest"),
        ("HIP_VISIBLE_DEVICES", f"{DEFAULT_IMAGE}:latest", None, f"{DEFAULT_IMAGE}:latest"),
        ("HIP_VISIBLE_DEVICES", None, f"{DEFAULT_IMAGE}:latest", f"{DEFAULT_IMAGE}:latest"),
    ],
)
@patch("ramalama.common.attempt_to_use_versioned")
def test_accel_image(mock_attempt_versioned, accel_env: str, env_override, config_override: str, expected_result: str):
    # We force the check for a versioned image to fail. This allows the test
    # to correctly verify the fallback logic to ':latest', making the test
    # independent of the actual images present on the host machine.
    mock_attempt_versioned.return_value = False

    with tempfile.NamedTemporaryFile('w', delete_on_close=False) as f:
        cmdline = []
        cmdline.extend(["run", "granite"])

        env = {}
        if config_override:
            f.write(
                f"""\
[ramalama]
image = "{config_override}"
                """
            )
            f.flush()
            env["RAMALAMA_CONFIG"] = f.name
        else:
            env["RAMALAMA_CONFIG"] = "/dev/null"

        if accel_env:
            env[accel_env] = "1"
        if env_override:
            env["RAMALAMA_IMAGE"] = env_override

        with patch.dict("os.environ", env, clear=True):

            config = default_config()
            with patch("ramalama.cli.CONFIG", config):
                parser = create_argument_parser("test_accel_image")
                configure_subcommands(parser)
                assert accel_image(config) == expected_result


@patch("ramalama.common.run_cmd")
@patch("ramalama.common.handle_provider")
def test_apple_vm_returns_result(mock_handle_provider, mock_run_cmd):
    mock_run_cmd.return_value.stdout = b'[{"Name": "myvm"}]'
    mock_handle_provider.return_value = True

    from ramalama.common import apple_vm

    result = apple_vm("podman")

    assert result is True
    mock_run_cmd.assert_called_once_with(
        ["podman", "machine", "list", "--format", "json", "--all-providers"], ignore_stderr=True
    )
    mock_handle_provider.assert_called_once_with({"Name": "myvm"})


class TestGetAccel:
    accels = [
        ("check_rocm_amd", "hip"),
        ("check_nvidia", "cuda"),
        ("check_mthreads", "musa"),
        ("check_intel", "intel"),
        ("check_ascend", "cann"),
        ("check_asahi", "asahi"),
    ]

    @pytest.mark.parametrize("accel,expected", accels)
    def test_get_accel(self, accel, expected):  # sourcery skip: no-loop-in-tests
        with ExitStack() as stack:
            for other_accel, _ in self.accels:
                return_value = expected if other_accel == accel else None
                stack.enter_context(patch(f"ramalama.common.{other_accel}", return_value=return_value))
            returned_accel = get_accel()
            assert returned_accel == expected

    def test_default_get_accel(self):  # sourcery skip: no-loop-in-tests
        with ExitStack() as stack:
            for other_accel, _ in self.accels:
                stack.enter_context(patch(f"ramalama.common.{other_accel}", return_value=None))
            returned_accel = get_accel()
            assert returned_accel == "none"
