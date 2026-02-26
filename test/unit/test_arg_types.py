import subprocess
from types import SimpleNamespace
from typing import Any, Protocol

import pytest

from ramalama.arg_types import GenerateArgType, _matches_type, narrow_by_schema


class GenerateInput:
    def __init__(self, gen_type: str = "kube", output_dir: str = "."):
        self.gen_type = gen_type
        self.output_dir = output_dir


class MissingGenerateField:
    def __init__(self):
        self.gen_type = "kube"


def test_matches_type_protocol_union_accepts_protocol_shape():
    value = GenerateInput()

    assert _matches_type(value, GenerateArgType | str | None)


def test_matches_type_protocol_union_rejects_missing_protocol_fields():
    value = MissingGenerateField()

    assert not _matches_type(value, GenerateArgType | str | None)


def test_matches_type_protocol_union_accepts_string_and_none():
    assert _matches_type("kube", GenerateArgType | str | None)
    assert _matches_type(None, GenerateArgType | str | None)


def test_matches_type_parameterized_generic_in_union():
    assert _matches_type(None, subprocess.Popen[Any] | None)


def test_matches_type_parameterized_generic_rejects_wrong_type():
    assert not _matches_type("not-a-process", subprocess.Popen[Any] | None)


def test_narrow_by_schema_is_shape_only():
    class ShapeOnlySchema(Protocol):
        count: int
        names: list[str]

    args = SimpleNamespace(count="not-an-int", names=123)

    narrowed = narrow_by_schema(args, ShapeOnlySchema)

    assert narrowed is args


def test_narrow_by_schema_raises_on_missing_field():
    class NeedsFieldSchema(Protocol):
        present: str
        missing: int

    args = SimpleNamespace(present="ok")

    with pytest.raises(ValueError, match="missing argument: missing"):
        narrow_by_schema(args, NeedsFieldSchema)
