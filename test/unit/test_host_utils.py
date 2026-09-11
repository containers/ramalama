import pytest

from ramalama.host_utils import (
    format_bind_host_for_connection,
    format_bind_host_for_url,
    format_bind_host_literal,
    format_bind_host_publish_prefix,
    format_vm_aware_publish_prefix,
    is_loopback_bind_host,
    localhost_from_bind_host,
    normalize_bind_host,
)


@pytest.mark.parametrize(
    "host, expected",
    [
        ("127.0.0.1", "127.0.0.1"),
        ("[::1]", "::1"),
        ("::", "::"),
        ("[fe80::1]", "fe80::1"),
        (None, ""),
        ("", ""),
    ],
)
def test_normalize_bind_host(host, expected):
    assert normalize_bind_host(host) == expected


@pytest.mark.parametrize(
    "host, expected",
    [
        ("0.0.0.0", "127.0.0.1"),
        ("::", "127.0.0.1"),
        ("[::]", "127.0.0.1"),
        ("127.0.0.1", "127.0.0.1"),
        ("::1", "::1"),
        ("192.168.1.100", "192.168.1.100"),
        (None, "127.0.0.1"),
        ("", "127.0.0.1"),
    ],
)
def test_localhost_from_bind_host(host, expected):
    assert localhost_from_bind_host(host) == expected


@pytest.mark.parametrize(
    "host, expected",
    [
        ("0.0.0.0", "127.0.0.1"),
        ("::", "127.0.0.1"),
        ("127.0.0.1", "127.0.0.1"),
        ("::1", "[::1]"),
        ("[::1]", "[::1]"),
        ("fe80::1", "[fe80::1]"),
        (None, "127.0.0.1"),
        ("", "127.0.0.1"),
    ],
)
def test_format_bind_host_for_url(host, expected):
    assert format_bind_host_for_url(host) == expected


@pytest.mark.parametrize(
    "host, expected",
    [
        ("0.0.0.0", "127.0.0.1"),
        ("::", "127.0.0.1"),
        ("[::]", "127.0.0.1"),
        ("127.0.0.1", "127.0.0.1"),
        ("::1", "::1"),
        (None, "127.0.0.1"),
        ("", "127.0.0.1"),
    ],
)
def test_format_bind_host_for_connection(host, expected):
    assert format_bind_host_for_connection(host) == expected


@pytest.mark.parametrize(
    "host, expected",
    [
        ("::", "[::]"),
        ("127.0.0.1", "127.0.0.1"),
        ("::1", "[::1]"),
        ("[::1]", "[::1]"),
        ("fe80::1", "[fe80::1]"),
        (None, ""),
        ("", ""),
    ],
)
def test_format_bind_host_literal(host, expected):
    assert format_bind_host_literal(host) == expected


@pytest.mark.parametrize(
    "host, expected",
    [
        ("::", ""),
        ("127.0.0.1", "127.0.0.1:"),
        ("localhost", "127.0.0.1:"),
        ("::1", "[::1]:"),
        ("[::1]", "[::1]:"),
        ("fe80::1", "[fe80::1]:"),
        (None, ""),
        ("", ""),
    ],
)
def test_format_bind_host_publish_prefix(host, expected):
    assert format_bind_host_publish_prefix(host) == expected


@pytest.mark.parametrize(
    "host, expected",
    [
        ("127.0.0.1", True),
        ("::1", True),
        ("[::1]", True),
        ("localhost", True),
        ("0.0.0.0", False),
        ("::", False),
        ("192.168.1.100", False),
        ("127.1.2.3", False),
        (None, False),
        ("", False),
    ],
)
def test_is_loopback_bind_host(host, expected):
    assert is_loopback_bind_host(host) == expected


@pytest.mark.parametrize(
    "system, host, expected",
    [
        # Native engines: identical to format_bind_host_publish_prefix.
        ("Linux", "127.0.0.1", "127.0.0.1:"),
        ("Linux", "::1", "[::1]:"),
        ("Linux", "0.0.0.0", "0.0.0.0:"),
        ("Linux", "::", ""),
        # VM-backed engines: a loopback bind is unreachable from the host, so the
        # prefix is dropped (publish inside the VM on all interfaces).
        ("Darwin", "127.0.0.1", ""),
        ("Windows", "::1", ""),
        ("Darwin", "localhost", ""),
        # A wildcard bind is reachable, so it is left unchanged even on a VM.
        ("Darwin", "0.0.0.0", "0.0.0.0:"),
        ("Windows", "::", ""),
    ],
)
def test_format_vm_aware_publish_prefix(monkeypatch, system, host, expected):
    monkeypatch.setattr("ramalama.host_utils.platform.system", lambda: system)
    assert format_vm_aware_publish_prefix(host) == expected
