import pytest

from ramalama.model_store.snapshot_file import SnapshotFile, SnapshotFileType, validate_snapshot_files

chat_template = SnapshotFile(name="chat-template", hash="", header={}, type=SnapshotFileType.ChatTemplate, url="")
model_file = SnapshotFile(name="model", hash="", header={}, type=SnapshotFileType.Model, url="")
other_file = SnapshotFile(name="other", hash="", header={}, type=SnapshotFileType.Other, url="")


@pytest.mark.parametrize(
    "input,expect_error",
    [
        ([], False),
        ([chat_template, model_file, other_file], False),
        ([chat_template, model_file, chat_template, other_file], True),
        ([chat_template, model_file, other_file, model_file], False),
        ([chat_template, model_file, chat_template, model_file, other_file], True),
    ],
)
def test_model_factory_create(input: list[SnapshotFile], expect_error: bool):
    if expect_error:
        with pytest.raises(Exception):
            validate_snapshot_files(input)
    else:
        validate_snapshot_files(input)
