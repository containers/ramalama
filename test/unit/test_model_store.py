import pytest

from ramalama.model_store.snapshot_file import SnapshotFile, SnapshotFileType, validate_snapshot_files

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
