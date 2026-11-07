"""Unit tests for the shared server side TLS helpers."""

import argparse
import os
import ssl

import pytest

from ramalama.tls import (
    MNT_TLS_CERT_FILE,
    MNT_TLS_KEY_FILE,
    add_tls_args,
    host_tls_paths,
    probe_ssl_context,
    tls_enabled,
    tls_mounts,
    tls_paths,
    validate_tls_args,
)


def make_ns(cert=None, key=None) -> argparse.Namespace:
    return argparse.Namespace(tls_cert_file=cert, tls_key_file=key)


class TestTLSPaths:
    def test_disabled_without_cert(self):
        ns = make_ns()

        assert not tls_enabled(ns)
        assert not host_tls_paths(ns)
        assert tls_mounts(ns) == []
        assert not tls_paths(ns, in_container=True)

    def test_half_configured_pair_raises(self):
        """A caller that skipped validate_tls_args must not quietly serve
        plain HTTP with the file the user supplied left unused."""
        for ns in (make_ns(cert="/host/tls.crt"), make_ns(key="/host/tls.key")):
            with pytest.raises(ValueError, match="must be specified together"):
                tls_mounts(ns)

    def test_missing_attributes_are_not_tls(self):
        """Callers that never registered the options still work."""
        assert not tls_enabled(argparse.Namespace())
        assert tls_mounts(argparse.Namespace()) == []

    def test_host_paths(self):
        ns = make_ns(cert="/host/tls.crt", key="/host/tls.key")

        assert tls_enabled(ns)
        assert tls_paths(ns, in_container=False) == host_tls_paths(ns)
        assert tls_paths(ns, in_container=False).cert == "/host/tls.crt"
        assert tls_paths(ns, in_container=False).key == "/host/tls.key"

    def test_container_paths(self):
        ns = make_ns(cert="/host/tls.crt", key="/host/tls.key")
        paths = tls_paths(ns, in_container=True)

        assert paths.cert == MNT_TLS_CERT_FILE
        assert paths.key == MNT_TLS_KEY_FILE

    def test_mounts(self):
        ns = make_ns(cert="/host/tls.crt", key="/host/tls.key")

        assert tls_mounts(ns) == [("/host/tls.crt", MNT_TLS_CERT_FILE), ("/host/tls.key", MNT_TLS_KEY_FILE)]


class TestAddTLSArgs:
    def test_cert_and_key(self):
        parser = argparse.ArgumentParser()
        add_tls_args(parser)

        args = parser.parse_args(["--tls-cert-file", "a.crt", "--tls-key-file", "a.key"])
        assert args.tls_cert_file == "a.crt"
        assert args.tls_key_file == "a.key"

    def test_defaults_to_disabled(self):
        parser = argparse.ArgumentParser()
        add_tls_args(parser)

        assert not tls_enabled(parser.parse_args([]))


class TestValidateTLSArgs:
    def test_no_tls_is_valid(self):
        validate_tls_args(make_ns())

    def test_cert_without_key(self):
        with pytest.raises(ValueError, match="must be specified together"):
            validate_tls_args(make_ns(cert="/host/tls.crt"))

    def test_key_without_cert(self):
        with pytest.raises(ValueError, match="must be specified together"):
            validate_tls_args(make_ns(key="/host/tls.key"))

    def test_missing_cert_file(self, tmp_path):
        key = tmp_path / "tls.key"
        key.write_text("key")

        with pytest.raises(ValueError, match="--tls-cert-file: no such file"):
            validate_tls_args(make_ns(cert=str(tmp_path / "absent.crt"), key=str(key)))

    def test_missing_key_file(self, tmp_path):
        cert = tmp_path / "tls.crt"
        cert.write_text("cert")

        with pytest.raises(ValueError, match="--tls-key-file: no such file"):
            validate_tls_args(make_ns(cert=str(cert), key=str(tmp_path / "absent.key")))

    def test_directory_is_not_a_file(self, tmp_path):
        key = tmp_path / "tls.key"
        key.write_text("key")

        with pytest.raises(ValueError, match="--tls-cert-file: no such file"):
            validate_tls_args(make_ns(cert=str(tmp_path), key=str(key)))

    def test_paths_are_made_absolute(self, tmp_path, monkeypatch):
        """Relative paths are bind mounted, so they have to be resolved while
        the working directory is still the user's."""
        (tmp_path / "tls.crt").write_text("cert")
        (tmp_path / "tls.key").write_text("key")
        monkeypatch.chdir(tmp_path)

        ns = make_ns(cert="tls.crt", key="tls.key")
        validate_tls_args(ns)

        assert ns.tls_cert_file == str(tmp_path / "tls.crt")
        assert ns.tls_key_file == str(tmp_path / "tls.key")

    def test_user_home_is_expanded(self, tmp_path, monkeypatch):
        (tmp_path / "tls.crt").write_text("cert")
        (tmp_path / "tls.key").write_text("key")
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(tmp_path), 1))

        ns = make_ns(cert="~/tls.crt", key="~/tls.key")
        validate_tls_args(ns)

        assert ns.tls_cert_file == str(tmp_path / "tls.crt")


class TestProbeSSLContext:
    def test_none_without_tls(self):
        assert probe_ssl_context(make_ns()) is None

    def test_does_not_verify_the_server(self):
        """The server is on loopback with a certificate RamaLama was just
        handed, so the probe has nothing to verify it against."""
        context = probe_ssl_context(make_ns(cert="/host/tls.crt", key="/host/tls.key"))

        assert context is not None
        assert context.check_hostname is False
        assert context.verify_mode == ssl.CERT_NONE
