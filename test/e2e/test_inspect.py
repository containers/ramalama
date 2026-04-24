import json
import re
from subprocess import STDOUT, CalledProcessError

import pytest

from test.e2e.utils import RamalamaExecWorkspace

GGUF_MODEL = "ollama://tinyllama"
ST_MODEL = "https://huggingface.co/LiheYoung/depth-anything-small-hf/resolve/main/model.safetensors"


@pytest.fixture(scope="module")
def shared_ctx():
    with RamalamaExecWorkspace() as ctx:
        ctx.check_call(["ramalama", "-q", "pull", GGUF_MODEL])
        ctx.check_call(["ramalama", "-q", "pull", ST_MODEL])
        yield ctx


@pytest.mark.e2e
def test_inspect_non_existent_model(shared_ctx):
    ctx = shared_ctx
    model_name = "non_existent_model_for_inspect"
    with pytest.raises(CalledProcessError) as exc_info:
        ctx.check_output(["ramalama", "inspect", model_name], stderr=STDOUT)
    assert exc_info.value.returncode == 22
    assert f"Error: No ref file found for '{model_name}'. Please pull model." in exc_info.value.output.decode("utf-8")


@pytest.mark.e2e
@pytest.mark.parametrize(
    "model_name, use_all_flag, expected_key, expected_value",
    [
        # GGUF inspect (no --all)
        pytest.param(GGUF_MODEL, False, ["Name"], "tinyllama", id="gguf_inspect_name"),
        pytest.param(GGUF_MODEL, False, ["Registry"], "ollama", id="gguf_inspect_registry"),
        pytest.param(GGUF_MODEL, False, ["Format"], "GGUF", id="gguf_inspect_format"),
        pytest.param(GGUF_MODEL, False, ["Version"], "3", id="gguf_inspect_version"),
        pytest.param(GGUF_MODEL, False, ["Endianness"], "0", id="gguf_inspect_endianness"),
        pytest.param(GGUF_MODEL, False, ["Metadata"], "23", id="gguf_inspect_metadata_count"),
        pytest.param(GGUF_MODEL, False, ["Tensors"], "201", id="gguf_inspect_tensors_count"),
        pytest.param(
            GGUF_MODEL,
            False,
            ["Path"],
            r".*store[\\/]+ollama[\\/]+library[\\/]+tinyllama.*",
            id="gguf_inspect_path",
        ),
        # Safetensors inspect (no --all)
        pytest.param(ST_MODEL, False, ["Name"], "model.safetensors", id="safetensors_inspect_name"),
        pytest.param(ST_MODEL, False, ["Registry"], "https", id="safetensors_inspect_registry"),
        pytest.param(ST_MODEL, False, ["Metadata"], "288", id="safetensors_inspect_metadata_count"),
        # GGUF inspect --all
        pytest.param(GGUF_MODEL, True, ["Name"], "tinyllama", id="gguf_inspect_all_name"),
        pytest.param(GGUF_MODEL, True, ["Registry"], "ollama", id="gguf_inspect_all_registry"),
        pytest.param(GGUF_MODEL, True, ["Format"], "GGUF", id="gguf_inspect_all_format"),
        pytest.param(GGUF_MODEL, True, ["Version"], "3", id="gguf_inspect_all_version"),
        pytest.param(
            GGUF_MODEL,
            True,
            ["Endianness"],
            "0",
            id="gguf_inspect_all_endianness",
        ),
        pytest.param(
            GGUF_MODEL, True, ["Metadata", "data", "general.architecture"], "llama", id="gguf_inspect_all_meta_arch"
        ),
        # Safetensors inspect --all
        pytest.param(ST_MODEL, True, ["Name"], "model.safetensors", id="safetensors_inspect_all_name"),
        pytest.param(ST_MODEL, True, ["Registry"], "https", id="safetensors_inspect_all_registry"),
        pytest.param(
            ST_MODEL, True, ["Header", "__metadata__", "format"], "pt", id="safetensors_inspect_all_header_format"
        ),
    ],
)
def test_inspect_model_json_output(shared_ctx, model_name, use_all_flag, expected_key, expected_value):
    ctx = shared_ctx
    result = ctx.check_output(["ramalama", "inspect", "--json"] + (["--all"] if use_all_flag else []) + [model_name])
    data = json.loads(result)

    value = data
    for k in expected_key:
        value = value[k]

    assert re.match(expected_value, str(value))


@pytest.mark.e2e
@pytest.mark.parametrize(
    "key, expected_value",
    [
        pytest.param("general.architecture", "llama", id="general.architecture"),
        pytest.param("general.file_type", "2", id="general.file_type"),
        pytest.param("general.name", "TinyLlama", id="general.name"),
        pytest.param("general.quantization_version", "2", id="general.quantization_version"),
        pytest.param("llama.attention.head_count", "32", id="llama.attention.head_count"),
        pytest.param("llama.attention.head_count_kv", "4", id="llama.attention.head_count_kv"),
        pytest.param(
            "llama.attention.layer_norm_rms_epsilon",
            "9.999999747378752e-06",
            id="llama.attention.layer_norm_rms_epsilon",
        ),
        pytest.param("llama.block_count", "22", id="llama.block_count"),
        pytest.param("llama.context_length", "2048", id="llama.context_length"),
        pytest.param("llama.embedding_length", "2048", id="llama.embedding_length"),
        pytest.param("llama.feed_forward_length", "5632", id="llama.feed_forward_length"),
        pytest.param("llama.rope.dimension_count", "64", id="llama.rope.dimension_count"),
        pytest.param("llama.rope.freq_base", "10000.0", id="llama.rope.freq_base"),
        pytest.param("tokenizer.ggml.bos_token_id", "1", id="tokenizer.ggml.bos_token_id"),
        pytest.param("tokenizer.ggml.eos_token_id", "2", id="tokenizer.ggml.eos_token_id"),
        pytest.param("tokenizer.ggml.model", "llama", id="tokenizer.ggml.model"),
        pytest.param("tokenizer.ggml.padding_token_id", "2", id="tokenizer.ggml.padding_token_id"),
        pytest.param("tokenizer.ggml.unknown_token_id", "0", id="tokenizer.ggml.unknown_token_id"),
    ],
)
def test_inspect_gguf_model_with_get(shared_ctx, key, expected_value):
    ctx = shared_ctx

    output = ctx.check_output(["ramalama", "inspect", "--get", key, GGUF_MODEL])
    assert output.strip() == expected_value

    output_all = ctx.check_output(["ramalama", "inspect", "--get", "all", GGUF_MODEL])
    assert f"{key}: {expected_value}" in output_all
