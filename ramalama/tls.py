"""Server side TLS (HTTPS) support for the inference runtimes.

RamaLama does not terminate TLS itself: it hands the user supplied
certificate and key to the inference server (llama.cpp's llama-server or
the vLLM OpenAI API server), which serves HTTPS directly. In container
mode the files are bind mounted read only under MNT_TLS_DIR, so the paths
passed to the server are the container paths rather than the host ones.
"""

from __future__ import annotations

import argparse
import os
import ssl
from dataclasses import dataclass
from typing import Optional

from ramalama.path_utils import get_container_mount_path

MNT_TLS_DIR = "/mnt/tls"
MNT_TLS_CERT_FILE = f"{MNT_TLS_DIR}/tls.crt"
MNT_TLS_KEY_FILE = f"{MNT_TLS_DIR}/tls.key"


@dataclass(frozen=True)
class TLSPaths:
    """Certificate and key paths, both empty when TLS is off."""

    cert: str = ""
    key: str = ""

    def __bool__(self) -> bool:
        return bool(self.cert)


def add_tls_args(parser: argparse.ArgumentParser) -> None:
    """Register the TLS options on a serve parser."""
    parser.add_argument(
        "--tls-cert-file",
        dest="tls_cert_file",
        help="PEM-encoded certificate, serve the REST API over HTTPS (requires --tls-key-file)",
    )
    parser.add_argument(
        "--tls-key-file",
        dest="tls_key_file",
        help="PEM-encoded private key matching --tls-cert-file",
    )


def host_tls_paths(args) -> TLSPaths:
    """The TLS files as they are named on the host.

    A half configured pair raises rather than reading as TLS being off,
    so a caller that never ran validate_tls_args cannot quietly fall back
    to plain HTTP with the key the user supplied left unused.
    """
    cert = getattr(args, "tls_cert_file", None) or ""
    key = getattr(args, "tls_key_file", None) or ""
    if bool(cert) != bool(key):
        raise ValueError("--tls-cert-file and --tls-key-file must be specified together")

    return TLSPaths(cert=cert, key=key)


def tls_enabled(args) -> bool:
    return bool(host_tls_paths(args))


def tls_paths(args, in_container: bool) -> TLSPaths:
    """The TLS files as the inference server sees them."""
    host = host_tls_paths(args)
    if not host or not in_container:
        return host

    return TLSPaths(cert=MNT_TLS_CERT_FILE, key=MNT_TLS_KEY_FILE)


def tls_mounts(args) -> list[tuple[str, str]]:
    """(host path, container path) pairs to bind mount, empty when TLS is off."""
    host = host_tls_paths(args)
    if not host:
        return []

    return [(host.cert, MNT_TLS_CERT_FILE), (host.key, MNT_TLS_KEY_FILE)]


def validate_tls_args(args) -> None:
    """Check the TLS options and rewrite them on args as absolute paths."""
    paths = host_tls_paths(args)
    if not paths:
        return

    for dest, option, path in (
        ("tls_cert_file", "--tls-cert-file", paths.cert),
        ("tls_key_file", "--tls-key-file", paths.key),
    ):
        resolved = os.path.abspath(os.path.expanduser(path))
        if not os.path.isfile(resolved):
            raise ValueError(f"{option}: no such file: {path}")
        setattr(args, dest, resolved)


_probe_context: Optional[ssl.SSLContext] = None


def probe_ssl_context(args) -> Optional[ssl.SSLContext]:
    """The SSL context for RamaLama's own readiness probe, None without TLS.

    The probe talks to a server RamaLama has just started on the loopback
    interface, over a certificate that is typically self-signed and issued
    for a name the probe does not connect to, so it deliberately does not
    verify it. The context is built once and shared: the probe runs once a
    second until the server answers, and loading the system trust store
    each time only to discard it is pure waste.
    """
    global _probe_context

    if not tls_enabled(args):
        return None

    if _probe_context is None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        _probe_context = context
    return _probe_context


def tls_mount_args(engine, args) -> list[str]:
    """Engine --mount arguments for the TLS files, empty when TLS is off."""
    return [
        f"--mount=type=bind,src={get_container_mount_path(host_path)},destination={dest},ro{engine.relabel()}"
        for host_path, dest in tls_mounts(args)
    ]
