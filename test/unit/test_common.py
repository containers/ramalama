import os
import shutil
from pathlib import Path
from sys import platform
from unittest.mock import Mock, patch

import pytest

from ramalama.common import rm_until_substring, verify_checksum, accel_image, DEFAULT_IMAGE


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
    "accel_env,image_opt,images_conf,image_conf,expected_result",
    [
        (None, None, DEFAULT_IMAGES, f"{DEFAULT_IMAGE}:latest", DEFAULT_IMAGE),
        ("HIP_VISIBLE_DEVICES", None, DEFAULT_IMAGES, DEFAULT_IMAGE, "quay.io/ramalama/rocm"),
        ("HIP_VISIBLE_DEVICES", DEFAULT_IMAGE, DEFAULT_IMAGES, DEFAULT_IMAGE, DEFAULT_IMAGE),
        ("HIP_VISIBLE_DEVICES", DEFAULT_IMAGE, DEFAULT_IMAGES, "quay.io/ramalama/rocm", DEFAULT_IMAGE),
        ("CUDA_VISIBLE_DEVICES", DEFAULT_IMAGE, DEFAULT_IMAGES, DEFAULT_IMAGE, DEFAULT_IMAGE),
    ],
)
def test_accel_image(accel_env: str, image_opt: str, images_conf: dict[str,str], image_conf: str, expected_result: str):
    with patch.dict('os.environ', {accel_env: "1"} if accel_env else {}, clear=True):
        args = Mock(return_value=None)
        args.image = image_opt
        args.rag = False
        args.container = False
        config = {"engine": "podman"}
        config["images"] = images_conf
        config["image"] = image_conf
        assert accel_image(config, args) == expected_result + ":latest"
