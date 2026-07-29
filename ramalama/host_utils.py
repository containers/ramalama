"""Utilities for normalizing and formatting bind host addresses."""

from __future__ import annotations

from typing import Optional

WILDCARD_BIND_HOSTS = frozenset({"0.0.0.0", "::"})


def normalize_bind_host(host: Optional[str]) -> str:
    """Remove surrounding brackets from a bind host value."""
    if not host:
        return ""
    return host.strip("[]")


def localhost_from_bind_host(host: Optional[str], *, loopback: str = "127.0.0.1") -> str:
    """Return loopback when host binds all interfaces, otherwise return the host."""
    if not host:
        return loopback
    normalized = normalize_bind_host(host)
    return loopback if normalized in WILDCARD_BIND_HOSTS else normalized


def format_bind_host_for_url(host: Optional[str]) -> str:
    """Format a bind host for use in an http URL authority (handles IPv6 bracketing)."""
    if not host:
        return "127.0.0.1"
    host = localhost_from_bind_host(host)
    return f"[{host}]" if ":" in host else host


def format_bind_host_for_connection(host: Optional[str], *, default: str = "127.0.0.1") -> str:
    """Format a bind host for HTTPConnection and similar clients."""
    if not host:
        return default
    return localhost_from_bind_host(host, loopback=default)


def format_bind_host_literal(host: Optional[str]) -> str:
    """Format a bind host for display or host:port binding without loopback substitution."""
    if not host:
        return ""
    normalized = normalize_bind_host(host)
    return f"[{normalized}]" if ":" in normalized else normalized


def format_bind_host_publish_prefix(host: Optional[str]) -> str:
    """Return host prefix for container publish-port arguments, or empty for IPv6 wildcard."""
    if not host:
        return ""
    normalized = normalize_bind_host(host)
    if normalized == "::":
        return ""
    return f"[{normalized}]:" if ":" in normalized else f"{normalized}:"
