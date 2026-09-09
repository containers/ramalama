import sys
from argparse import Namespace
from unittest import mock

import pytest

from ramalama.cli import (
    ParsedGenerateInput,
    _normalize_engine_args,
    daemon_start_cli,
    parse_generate_option,
    post_parse_setup,
)
from ramalama.transports.base import NoGGUFModelFileFound, SafetensorModelNotSupported


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


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, []),
        ("", []),
        ("--label=a=1", ["--label=a=1"]),
        (["--label=a=1", "--label=b=2"], ["--label=a=1", "--label=b=2"]),
        (
            ["--env FOO=bar", "--mount type=bind,src=/tmp,dst=/mnt"],
            ["--env", "FOO=bar", "--mount", "type=bind,src=/tmp,dst=/mnt"],
        ),
    ],
)
def test_normalize_engine_args(raw, expected):
    assert _normalize_engine_args(raw) == expected


def test_post_parse_setup_engine_args_repeated():
    ns = Namespace(engine_args=["--label=a=1", "--label=b=2"], debug=False)
    post_parse_setup(ns)
    assert ns.engine_args == ["--label=a=1", "--label=b=2"]


@pytest.mark.parametrize(
    "input_args, expected_initial, expected_unresolved, expected_resolved",
    [
        (
            Namespace(MODEL="https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v0.6/blob/main/ggml-model-q4_0.gguf"),
            "https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v0.6/blob/main/ggml-model-q4_0.gguf",
            "https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v0.6/blob/main/ggml-model-q4_0.gguf",
            "https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v0.6/blob/main/ggml-model-q4_0.gguf",
        ),
        (
            Namespace(MODEL="https://hf.co/mlx-community/Kimi-Linear-48B-A3B-Instruct-4bit"),
            "https://hf.co/mlx-community/Kimi-Linear-48B-A3B-Instruct-4bit",
            "hf://mlx-community/Kimi-Linear-48B-A3B-Instruct-4bit",
            "hf://mlx-community/Kimi-Linear-48B-A3B-Instruct-4bit",
        ),
        (
            Namespace(MODEL="https://ollama.com/library/smollm:135m"),
            "https://ollama.com/library/smollm:135m",
            "ollama://library/smollm:135m",
            "ollama://library/smollm:135m",
        ),
        (
            Namespace(MODEL="ollama.com/library/smollm:135m"),
            "ollama.com/library/smollm:135m",
            "ollama://library/smollm:135m",
            "ollama://library/smollm:135m",
        ),
        (Namespace(MODEL="tinyllama"), "tinyllama", "tinyllama", "hf://TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF"),
        (
            Namespace(
                MODEL=[
                    "https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v0.6/blob/main/ggml-model-q4_0.gguf",
                    "https://hf.co/mlx-community/Kimi-Linear-48B-A3B-Instruct-4bit",
                ]
            ),
            [
                "https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v0.6/blob/main/ggml-model-q4_0.gguf",
                "https://hf.co/mlx-community/Kimi-Linear-48B-A3B-Instruct-4bit",
            ],
            [
                "https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v0.6/blob/main/ggml-model-q4_0.gguf",
                "hf://mlx-community/Kimi-Linear-48B-A3B-Instruct-4bit",
            ],
            [
                "https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v0.6/blob/main/ggml-model-q4_0.gguf",
                "hf://mlx-community/Kimi-Linear-48B-A3B-Instruct-4bit",
            ],
        ),
    ],
)
def test_post_parse_setup_model_input(
    input_args: Namespace, expected_initial: str, expected_unresolved: str, expected_resolved: str
):
    input_args.debug = False
    post_parse_setup(input_args)

    assert hasattr(input_args, "INITIAL_MODEL"), "parsed arguments should always have INITIAL_MODEL field"
    assert hasattr(input_args, "UNRESOLVED_MODEL"), "parsed arguments should always have RESOLVED_MODEL field"

    assert input_args.INITIAL_MODEL == expected_initial
    assert input_args.UNRESOLVED_MODEL == expected_unresolved
    assert input_args.MODEL == expected_resolved
    assert input_args.model == input_args.MODEL


def _daemon_start_args(**overrides) -> Namespace:
    args = Namespace(
        container=True,
        engine="podman",
        store="/tmp/store",
        port="1234",
        host="127.0.0.1",
        pull="missing",
        image="testimage",
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def _capture_daemon_cmd(args) -> list:
    with mock.patch("ramalama.cli.exec_cmd") as exec_cmd:
        daemon_start_cli(args)
    assert exec_cmd.call_count == 1
    return exec_cmd.call_args.args[0]


@pytest.mark.parametrize(
    "host,expected_publish",
    [
        # loopback default must restrict the host-side publish to loopback
        ("127.0.0.1", "127.0.0.1:1234:8080"),
        # localhost normalizes to the IPv4 literal podman -p requires
        ("localhost", "127.0.0.1:1234:8080"),
        ("::1", "[::1]:1234:8080"),
        # wildcard opt-in publishes on all interfaces (no host prefix)
        ("::", "1234:8080"),
        ("0.0.0.0", "0.0.0.0:1234:8080"),
    ],
)
def test_daemon_start_container_publish_respects_host(monkeypatch, host, expected_publish):
    # Pin a native engine so the host-side publish prefix is platform-independent;
    # the VM-backed loopback-drop behavior is covered separately below.
    monkeypatch.setattr("ramalama.host_utils.platform.system", lambda: "Linux")
    cmd = _capture_daemon_cmd(_daemon_start_args(host=host))
    # -p <publish> pair
    assert "-p" in cmd
    assert cmd[cmd.index("-p") + 1] == expected_publish
    # The daemon inside the container still binds the wildcard so the published
    # port can reach it, regardless of the host-side bind.
    from ramalama.config import get_wildcard_host

    assert cmd[cmd.index("--host") + 1] == get_wildcard_host()


def test_daemon_start_nocontainer_honors_host():
    cmd = _capture_daemon_cmd(_daemon_start_args(container=False, host="127.0.0.1"))
    # No container run wrapper, no port publish; daemon binds the requested host.
    assert "-p" not in cmd
    assert cmd[cmd.index("--host") + 1] == "127.0.0.1"


def test_daemon_start_container_publish_vm_backed_drops_loopback(monkeypatch):
    # On VM-backed engines (macOS/Windows) a loopback publish is bound inside the
    # VM and unreachable from the host, so the daemon path must drop the prefix
    # just like serve does, publishing on all interfaces inside the VM.
    monkeypatch.setattr("ramalama.host_utils.platform.system", lambda: "Darwin")
    cmd = _capture_daemon_cmd(_daemon_start_args(host="127.0.0.1"))
    assert cmd[cmd.index("-p") + 1] == "1234:8080"
