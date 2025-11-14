"""
Proxy support for RamaLama network operations.

This module provides support for HTTP, HTTPS, and SOCKS proxies through
standard environment variables.

Supported environment variables (case-insensitive):
- HTTP_PROXY: Proxy for HTTP connections
- HTTPS_PROXY: Proxy for HTTPS connections
- NO_PROXY: Comma-separated list of hosts to bypass proxy

Proxy URL formats:
- HTTP/HTTPS: http://proxy:port or https://proxy:port
- SOCKS4: socks4://proxy:port
- SOCKS5: socks5://proxy:port or socks5h://proxy:port (for DNS through proxy)
"""

import urllib.request

from ramalama.logger import logger


def _get_proxy_env() -> dict[str, str]:
    """
    Get proxy settings from environment variables using urllib's built-in function.

    Returns a dictionary with scheme -> proxy URL mappings.
    Uses urllib.request.getproxies_environment() which handles standard proxy
    environment variables (HTTP_PROXY, HTTPS_PROXY, NO_PROXY, etc.) in a
    case-insensitive manner.
    """
    proxy_env = urllib.request.getproxies_environment()

    for key, value in proxy_env.items():
        logger.debug(f"Found proxy setting: {key}_proxy={value}")

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
    has_socks = any(_is_socks_proxy(url) for url in proxy_env.values())

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

    # Build the proxy handler
    proxy_handler = urllib.request.ProxyHandler(proxy_env)
    opener = urllib.request.build_opener(proxy_handler)
    urllib.request.install_opener(opener)

    # Log configured proxies
    for key, value in proxy_env.items():
        if key != 'no':
            logger.info(f"Using proxy: {key}={value}")
        else:
            logger.debug(f"Proxy bypass list: {value}")


def get_proxy_info() -> dict[str, str]:
    """
    Get current proxy configuration for informational purposes.

    Returns:
        Dictionary with proxy configuration details
    """
    return _get_proxy_env()
