import os

from ramalama.compat import NamedTemporaryFile, StrEnum


def test_NamedTemporaryFile_delete_on_context_exit():
    try:
        with NamedTemporaryFile() as f:
            assert os.path.exists(f.name)
        assert not os.path.exists(f.name)
    finally:
        if os.path.exists(f.name):
            os.unlink(f.name)


def test_NamedTemporaryFile_delete_on_close():
    try:
        with NamedTemporaryFile() as f:
            assert os.path.exists(f.name)
            f.close()
            assert not os.path.exists(f.name)
    finally:
        if os.path.exists(f.name):
            os.unlink(f.name)


def test_NamedTemporaryFile_no_delete():
    try:
        with NamedTemporaryFile(delete=False) as f:
            assert os.path.exists(f.name)
        assert os.path.exists(f.name)
    finally:
        if os.path.exists(f.name):
            os.unlink(f.name)


def test_NamedTemporaryFile_no_delete_on_close():
    try:
        with NamedTemporaryFile(delete_on_close=False) as f:
            assert os.path.exists(f.name)
            f.close()
            assert os.path.exists(f.name)
        assert not os.path.exists(f.name)
    finally:
        if os.path.exists(f.name):
            os.unlink(f.name)


def test_StrEnum():
    class TestEnum(StrEnum):
        A = "a"
        B = "b"
        C = "c"

    assert TestEnum.A == "a"
    assert TestEnum.B == "b"
    assert TestEnum.C == "c"
    assert str(TestEnum.A) == "a"
    assert str(TestEnum.B) == "b"
    assert str(TestEnum.C) == "c"
    assert repr(TestEnum.A) == "<TestEnum.A: 'a'>"
    assert repr(TestEnum.B) == "<TestEnum.B: 'b'>"
    assert repr(TestEnum.C) == "<TestEnum.C: 'c'>"
    assert TestEnum.A.value == "a"
    assert TestEnum.B.value == "b"
    assert TestEnum.C.value == "c"
    assert TestEnum.A.name == "A"
    assert TestEnum.B.name == "B"
    assert TestEnum.C.name == "C"
