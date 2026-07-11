import pytest

from ramalama.host_utils import (
    format_bind_host_for_connection,
    format_bind_host_for_url,
    format_bind_host_literal,
    format_bind_host_publish_prefix,
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
        ("::1", "[::1]:"),
        ("[::1]", "[::1]:"),
        ("fe80::1", "[fe80::1]:"),
        (None, ""),
        ("", ""),
    ],
)
def test_format_bind_host_publish_prefix(host, expected):
    assert format_bind_host_publish_prefix(host) == expected
