"""
Proxy support for RamaLama network operations.

This module provides support for HTTP, HTTPS, and SOCKS proxies through
standard environment variables.

Supported environment variables (case-insensitive):
- ALL_PROXY: Default proxy for all protocols
- HTTP_PROXY: Proxy for HTTP connections
- HTTPS_PROXY: Proxy for HTTPS connections
- NO_PROXY: Comma-separated list of hosts to bypass proxy

Proxy URL formats:
- HTTP/HTTPS: http://proxy:port or https://proxy:port
- SOCKS4: socks4://proxy:port
- SOCKS5: socks5://proxy:port or socks5h://proxy:port (for DNS through proxy)
"""

import os
import urllib.request

from ramalama.logger import logger


def _get_proxy_env() -> dict[str, str | None]:
    """
    Get proxy settings from environment variables.

    Returns a dictionary with lowercase keys for all proxy-related env vars.
    Checks both lowercase and uppercase variants of each variable.
    """
    proxy_vars = ['http_proxy', 'https_proxy', 'all_proxy', 'no_proxy']
    proxy_env: dict[str, str | None] = {}

    for var in proxy_vars:
        if value := os.environ.get(var) or os.environ.get(var.upper()):
            proxy_env[var] = value
            logger.debug(f"Found proxy setting: {var}={value}")

    return proxy_env


def _is_socks_proxy(proxy_url: str) -> bool:
    """Check if the proxy URL is a SOCKS proxy."""
    return proxy_url.startswith('socks4://') or proxy_url.startswith('socks5://') or proxy_url.startswith('socks5h://')


def setup_proxy_support() -> None:
    """
    Configure urllib to use proxy settings from environment variables.

    This function should be called once at application startup to configure
    proxy support for all urllib operations.

    Supports HTTP, HTTPS, and SOCKS proxies through standard environment variables.
    SOCKS proxy support requires the PySocks library to be installed.
    """
    proxy_env = _get_proxy_env()

    if not proxy_env:
        logger.debug("No proxy environment variables found")
        return

    # Check if any SOCKS proxies are configured
    has_socks = any(_is_socks_proxy(url) for url in proxy_env.values() if url)

    if has_socks:
        try:
            import socket  # noqa: F401

            import socks  # type: ignore  # noqa: F401

            # The import of socks monkey-patches socket, so we need to rebuild the urllib opener
            logger.debug("SOCKS proxy support enabled via PySocks")
        except ImportError:
            logger.warning(
                "SOCKS proxy configured but PySocks library not installed. "
                "Install it with: pip install 'PySocks[socks]'"
            )
            # Fall back to trying without SOCKS support
            pass

    # Build the proxy handler (filter out None values for type safety)
    proxy_dict: dict[str, str] = {k: v for k, v in proxy_env.items() if v is not None}
    proxy_handler = urllib.request.ProxyHandler(proxy_dict)
    opener = urllib.request.build_opener(proxy_handler)
    urllib.request.install_opener(opener)

    # Log configured proxies
    for key, value in proxy_env.items():
        if value and key != 'no_proxy':
            logger.info(f"Using proxy: {key}={value}")
        elif key == 'no_proxy':
            logger.debug(f"Proxy bypass list: {value}")


def get_proxy_info() -> dict[str, str]:
    """
    Get current proxy configuration for informational purposes.

    Returns:
        Dictionary with proxy configuration details
    """
    proxy_env = _get_proxy_env()
    return {k: v or "not set" for k, v in proxy_env.items()}
