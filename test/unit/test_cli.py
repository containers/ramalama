import sys
from unittest import mock

import pytest

from ramalama.cli import ParsedGenerateInput, parse_generate_option
from ramalama.model import NoGGUFModelFileFound, SafetensorModelNotSupported


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


@pytest.mark.parametrize(
    "duration, expected",
    [
        (0, "Less than a second"),
        (1, "1 second"),
        (2, "2 seconds"),
        (59, "59 seconds"),
        (60, "1 minute"),
        (120, "2 minutes"),
        (3600, "1 hour"),
        (7200, "2 hours"),
        (86400, "1 day"),
        (172800, "2 days"),
        (604800, "1 week"),
        (1209600, "2 weeks"),
        (2419200, "1 month"),
        (4838400, "2 months"),
        (31536000, "1 year"),
        (63072000, "2 years"),
        (315576000, "10 years"),
        (3155760000, "100 years"),
    ],
)
def test_human_duration(duration: int, expected: str):
    from ramalama.cli import human_duration

    assert human_duration(duration) == expected


@pytest.mark.parametrize(
    "args",
    [
        (["--help"]),
    ],
)
def test_help(args: list):
    from ramalama.cli import HelpException, help_cli

    with pytest.raises(HelpException):
        help_cli(args)


# Test human readable size
@pytest.mark.parametrize(
    "size, expected",
    [
        (0, "0 B"),
        (1, "1 B"),
        (1024, "1.0 KB"),
        (2048, "2.0 KB"),
        (1048576, "1.0 MB"),
        (2097152, "2.0 MB"),
        (1073741824, "1.0 GB"),
        (1610612736, "1.5 GB"),
        (2147483648, "2.0 GB"),
        (1099511627776, "1.0 TB"),
        (2199023255552, "2.0 TB"),
    ],
)
def test_human_readable_size(size: int, expected: str):
    from ramalama.cli import human_readable_size

    assert human_readable_size(size) == expected


# Test repr() for ParsedGenerateInput
@pytest.mark.parametrize(
    "input, expected",
    [
        (ParsedGenerateInput("kube", "."), "kube"),
        (ParsedGenerateInput("kube/quadlet", "."), "kube/quadlet"),
        (ParsedGenerateInput("kube", "/tmp"), "kube"),
        (ParsedGenerateInput("kube/quadlet", "/tmp"), "kube/quadlet"),
    ],
)
def test_parsed_generate_input_repr(input: ParsedGenerateInput, expected: str):
    assert repr(input) == expected


@pytest.mark.parametrize(
    "exc_type",
    [
        NoGGUFModelFileFound,
        SafetensorModelNotSupported,
    ],
)
def test_main_doesnt_crash_on_exc(monkeypatch, exc_type):
    from ramalama.cli import main

    monkeypatch.setattr(sys, "argv", ["ramalama", "inspect", "nonexistent-model"])
    with pytest.raises(SystemExit):
        with mock.patch("ramalama.cli.inspect_cli", side_effect=exc_type):
            main()


@pytest.mark.parametrize(
    "option, value",
    [
        (None, True),
        ("yes", True),
        ("on", True),
        ("1", True),
        ("no", False),
        ("off", False),
        ("0", False),
    ],
)
def test_pull_verify(monkeypatch, option, value):
    from ramalama.cli import init_cli

    argv = ["ramalama", "pull"]
    if option:
        argv.append(f"--verify={option}")
    argv.append("model")
    monkeypatch.setattr(sys, "argv", argv)
    parser, args = init_cli()
    assert hasattr(args, "verify")
    assert args.verify == value
