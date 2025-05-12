import pytest

from ramalama.cli import ParsedGenerateInput, parse_generate_option


@pytest.mark.parametrize(
    "input,expected",
    [
        ("kube", ParsedGenerateInput("kube", ".")),
        ("quadlet", ParsedGenerateInput("quadlet", ".")),
        ("kube/quadlet", ParsedGenerateInput("kube/quadlet", ".")),
        ("kube:/tmp", ParsedGenerateInput("kube", "/tmp")),
        ("quadlet:/tmp", ParsedGenerateInput("quadlet", "/tmp")),
        ("kube/quadlet:/tmp", ParsedGenerateInput("kube/quadlet", "/tmp")),
        ("kub", ParsedGenerateInput("kub", ".")),
        ("quadet", ParsedGenerateInput("quadet", ".")),
        ("kube-quadlet", ParsedGenerateInput("kube-quadlet", ".")),
        ("kub:/tmp", ParsedGenerateInput("kub", "/tmp")),
        ("quadet:/tmp", ParsedGenerateInput("quadet", "/tmp")),
        ("kube-quadlet:/tmp", ParsedGenerateInput("kube-quadlet", "/tmp")),
    ],
)
def test_parse_generate_option(input: str, expected: ParsedGenerateInput):
    out = parse_generate_option(input)
    assert out.gen_type == expected.gen_type
    assert out.output_dir == expected.output_dir


@pytest.mark.parametrize(
    "input,expected",
    [
        (ParsedGenerateInput("kube", "."), "kube"),
        (ParsedGenerateInput("kube/quadlet", "."), "kube/quadlet"),
    ],
)
def test_parse_generate_input_str(input: str, expected: str):
    assert str(input) == expected


@pytest.mark.parametrize(
    "input,compare,expected",
    [
        (ParsedGenerateInput("kube", "."), "kube", True),
        (ParsedGenerateInput("kube/quadlet", "/tmp"), "kube/quadlet", True),
        (ParsedGenerateInput("kuba", "."), "kube", False),
        (ParsedGenerateInput("kuba/quadlet", "/tmp"), "kube/quadlet", False),
    ],
)
def test_parse_generate_input_eq(input: str, compare: str, expected: bool):
    if expected:
        input == compare
    else:
        input != compare
