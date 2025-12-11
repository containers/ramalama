from ramalama.compat import StrEnum

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