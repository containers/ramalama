import os

import pytest

from ramalama.common import generate_sha256_binary
from ramalama.model_store.global_store import GlobalModelStore
from ramalama.model_store.reffile import RefJSONFile, StoreFile, StoreFileType
from ramalama.model_store.snapshot_file import (
    LocalSnapshotFile,
    SnapshotFile,
    SnapshotFileType,
    validate_snapshot_files,
)
from ramalama.model_store.store import ModelStore
from ramalama.model_store.template_conversion import wrap_template_with_messages_loop

chat_template = SnapshotFile(name="chat-template", hash="", header={}, type=SnapshotFileType.ChatTemplate, url="")
gguf_model_file = SnapshotFile(name="model", hash="", header={}, type=SnapshotFileType.GGUFModel, url="")
safetensor_model_file = SnapshotFile(name="model", hash="", header={}, type=SnapshotFileType.SafetensorModel, url="")
other_file = SnapshotFile(name="other", hash="", header={}, type=SnapshotFileType.Other, url="")


@pytest.mark.parametrize(
    "input,expect_error",
    [
        ([], False),
        ([chat_template, gguf_model_file, other_file], False),
        ([chat_template, gguf_model_file, chat_template, other_file], True),
        ([chat_template, gguf_model_file, other_file, gguf_model_file], False),
        ([chat_template, gguf_model_file, chat_template, gguf_model_file, other_file], True),
        ([chat_template, gguf_model_file, chat_template, safetensor_model_file, other_file], True),
    ],
)
def test_model_factory_create(input: list[SnapshotFile], expect_error: bool):
    if expect_error:
        with pytest.raises(Exception):
            validate_snapshot_files(input)
    else:
        validate_snapshot_files(input)


def test_try_convert_existing_chat_template_converts_flat_jinja(tmp_path, monkeypatch):
    base_path = tmp_path
    global_store = GlobalModelStore(str(base_path))
    model_store = ModelStore(global_store, model_name="sample", model_type="file", model_organization="org")
    model_store.ensure_directory_setup()

    model_tag = "latest"
    snapshot_hash = "snap123"
    chat_hash = "chat123"
    chat_filename = "chat_template"

    ref_path = model_store.get_ref_file_path(model_tag)
    os.makedirs(os.path.dirname(ref_path), exist_ok=True)
    ref = RefJSONFile(
        hash=snapshot_hash,
        path=ref_path,
        files=[StoreFile(chat_hash, chat_filename, StoreFileType.CHAT_TEMPLATE)],
    )
    ref.write_to_file()

    blob_path = model_store.get_blob_file_path(chat_hash)
    os.makedirs(os.path.dirname(blob_path), exist_ok=True)
    original_template = """{% if system %}<|system|>
{{ system }}<|end|>
{% endif %}{% if prompt %}<|user|>
{{ prompt }}<|end|>
{% endif %}"""
    with open(blob_path, "w") as chat_file:
        chat_file.write(original_template)

    captured = {}

    def fake_update_snapshot(ref_file_arg, snapshot_hash_arg, files):
        captured["ref_file"] = ref_file_arg
        captured["snapshot_hash"] = snapshot_hash_arg
        captured["files"] = files
        return True

    monkeypatch.setattr(model_store, "_update_snapshot", fake_update_snapshot)

    converted = model_store._try_convert_existing_chat_template(ref, snapshot_hash)

    assert converted is True
    assert captured["ref_file"] == ref
    assert captured["snapshot_hash"] == snapshot_hash
    assert len(captured["files"]) == 1
    converted_file = captured["files"][0]
    assert converted_file.type == SnapshotFileType.ChatTemplate
    assert converted_file.content == wrap_template_with_messages_loop(original_template).encode("utf-8")


def test_local_snapshot_file_binary_download_and_digest(tmp_path):
    # Use a payload that includes a null byte to ensure we are truly treating this as binary data
    content = b"binary-\x00-test-content"
    expected_digest = generate_sha256_binary(content)

    # Create a LocalSnapshotFile with known binary content
    snapshot_file = LocalSnapshotFile(
        name="test.bin",
        type=SnapshotFileType.Other,
        content=content,
    )

    # Act: download to a temporary path
    target_path = tmp_path / "downloaded.bin"
    snapshot_file.download(target_path, tmp_path)

    # Assert: file contents are exactly what we provided
    on_disk = target_path.read_bytes()
    assert on_disk == content

    # Assert: digest matches generate_sha256_binary(content)
    assert snapshot_file.hash == expected_digest
