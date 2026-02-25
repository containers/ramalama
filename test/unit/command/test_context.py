import argparse
from typing import Any
from unittest.mock import MagicMock

import pytest

from ramalama.command import context


@pytest.mark.parametrize(
    "args_dict",
    [
        {},
        {
            "host": "192.168.178.1",
            "port": 1337,
            "thinking": False,
            "context": 512,
            "temp": 11,
            "debug": True,
            "webui": True,
            "ngl": 44,
            "threads": 8,
            "logfile": "/var/tmp/ramalama.log",
            "container": True,
            "model_draft": "draft",
            "seed": 12345,
            "runtime_args": "--another-arg 44 --more-args",
            "cache_reuse": 1024,
        },
        {
            "host": "192.168.178.1",
            "port": 1337,
            "thinking": False,
            "container": True,
            "model_draft": "draft",
        },
        {
            "doesntexist": "not added to context",
        },
    ],
)
def test_ramalama_args_context(args_dict: dict[str, Any]):
    # Since there can be differences in names between the cli args to context arg
    # this mapping is used to identify them and use the right name for this test
    RAMALAMA_ARGS_CONTEXT_MAPPING = {
        "ctx_size": "context",
    }

    ctx = context.RamalamaArgsContext.from_argparse(argparse.Namespace(**args_dict))
    for ctx_field, ctx_value in ctx.__dict__.items():
        ctx_field = (
            ctx_field if ctx_field not in RAMALAMA_ARGS_CONTEXT_MAPPING else RAMALAMA_ARGS_CONTEXT_MAPPING[ctx_field]
        )
        if ctx_field in args_dict:
            expected_value = args_dict[ctx_field]
            assert ctx_value == expected_value, (
                f"Field '{ctx_field}' expected to be '{expected_value}', but got '{ctx_value}'"
            )
        else:
            assert ctx_value is None, f"Field '{ctx_field}' expected to be None in args context"


@pytest.mark.parametrize(
    "is_container, should_generate, dry_run",
    [
        (True, True, False),
        (False, True, True),
        (True, False, True),
        (False, False, False),
    ],
)
def test_ramalama_model_context_properties(is_container, should_generate, dry_run):
    mock_model = MagicMock()
    mock_model.model_name = "smollm"
    mock_model.model_tag = "135m"
    mock_model.model_organization = "mock-org"
    mock_model.model_alias = "mock-org/smollm"

    mock_model._get_entry_model_path.return_value = "/path/to/model"
    mock_model._get_mmproj_path.return_value = "/path/to/mmproj"
    mock_model._get_chat_template_path.return_value = "/path/to/chat-template"

    mock_draft_model = MagicMock()
    mock_draft_model._get_entry_model_path.return_value = "/path/to/draft-model"
    mock_model.draft_model = mock_draft_model

    ctx = context.RamalamaModelContext(
        model=mock_model,
        is_container=is_container,
        should_generate=should_generate,
        dry_run=dry_run,
    )

    assert ctx.name == "smollm:135m"
    assert ctx.alias == "mock-org/smollm"
    assert ctx.model_path == "/path/to/model"
    assert ctx.mmproj_path == "/path/to/mmproj"
    assert ctx.chat_template_path == "/path/to/chat-template"
    assert ctx.draft_model_path == "/path/to/draft-model"

    mock_model._get_entry_model_path.assert_called_with(is_container, should_generate, dry_run)
    mock_model._get_mmproj_path.assert_called_with(is_container, should_generate, dry_run)
    mock_model._get_chat_template_path.assert_called_with(is_container, should_generate, dry_run)
    mock_draft_model._get_entry_model_path.assert_called_with(is_container, should_generate, dry_run)


def test_ramalama_model_context_without_draft_model():
    # Pass in a dummy model which does not have the draft_model attribute
    class DummyModel:
        pass

    ctx = context.RamalamaModelContext(
        model=DummyModel(),
        is_container=False,
        should_generate=False,
        dry_run=True,
    )

    assert ctx.draft_model_path == ""
