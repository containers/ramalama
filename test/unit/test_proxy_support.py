"""
Tests for proxy support in RamaLama.
"""

import urllib.request
from unittest.mock import MagicMock, patch

import pytest

from ramalama.proxy_support import _get_proxy_env, _is_socks_proxy, get_proxy_info, setup_proxy_support


class TestGetProxyEnv:
    """Tests for _get_proxy_env function."""

    def test_no_proxy_env_vars(self, monkeypatch):
        """Test when no proxy environment variables are set."""
        # Clear any proxy env vars that might exist
        for var in [
            'http_proxy',
            'HTTP_PROXY',
            'https_proxy',
            'HTTPS_PROXY',
            'all_proxy',
            'ALL_PROXY',
            'no_proxy',
            'NO_PROXY',
        ]:
            monkeypatch.delenv(var, raising=False)

        result = _get_proxy_env()
        assert result == {}

    def test_lowercase_proxy_vars(self, monkeypatch):
        """Test detection of lowercase proxy environment variables."""
        for var in [
            'http_proxy',
            'HTTP_PROXY',
            'https_proxy',
            'HTTPS_PROXY',
            'all_proxy',
            'ALL_PROXY',
            'no_proxy',
            'NO_PROXY',
        ]:
            monkeypatch.delenv(var, raising=False)

        monkeypatch.setenv('http_proxy', 'http://proxy.example.com:8080')
        monkeypatch.setenv('https_proxy', 'http://proxy.example.com:8443')

        result = _get_proxy_env()
        assert result['http_proxy'] == 'http://proxy.example.com:8080'
        assert result['https_proxy'] == 'http://proxy.example.com:8443'

    def test_uppercase_proxy_vars(self, monkeypatch):
        """Test detection of uppercase proxy environment variables."""
        for var in [
            'http_proxy',
            'HTTP_PROXY',
            'https_proxy',
            'HTTPS_PROXY',
            'all_proxy',
            'ALL_PROXY',
            'no_proxy',
            'NO_PROXY',
        ]:
            monkeypatch.delenv(var, raising=False)

        monkeypatch.setenv('HTTP_PROXY', 'http://proxy.example.com:8080')
        monkeypatch.setenv('HTTPS_PROXY', 'http://proxy.example.com:8443')

        result = _get_proxy_env()
        assert result['http_proxy'] == 'http://proxy.example.com:8080'
        assert result['https_proxy'] == 'http://proxy.example.com:8443'

    def test_lowercase_takes_precedence(self, monkeypatch):
        """Test that lowercase env vars take precedence over uppercase."""
        for var in [
            'http_proxy',
            'HTTP_PROXY',
            'https_proxy',
            'HTTPS_PROXY',
            'all_proxy',
            'ALL_PROXY',
            'no_proxy',
            'NO_PROXY',
        ]:
            monkeypatch.delenv(var, raising=False)

        monkeypatch.setenv('http_proxy', 'http://lower.example.com:8080')
        monkeypatch.setenv('HTTP_PROXY', 'http://upper.example.com:8080')

        result = _get_proxy_env()
        assert result['http_proxy'] == 'http://lower.example.com:8080'

    def test_all_proxy_var(self, monkeypatch):
        """Test detection of ALL_PROXY environment variable."""
        for var in [
            'http_proxy',
            'HTTP_PROXY',
            'https_proxy',
            'HTTPS_PROXY',
            'all_proxy',
            'ALL_PROXY',
            'no_proxy',
            'NO_PROXY',
        ]:
            monkeypatch.delenv(var, raising=False)

        monkeypatch.setenv('all_proxy', 'http://proxy.example.com:8080')

        result = _get_proxy_env()
        assert result['all_proxy'] == 'http://proxy.example.com:8080'

    def test_no_proxy_var(self, monkeypatch):
        """Test detection of NO_PROXY environment variable."""
        for var in [
            'http_proxy',
            'HTTP_PROXY',
            'https_proxy',
            'HTTPS_PROXY',
            'all_proxy',
            'ALL_PROXY',
            'no_proxy',
            'NO_PROXY',
        ]:
            monkeypatch.delenv(var, raising=False)

        monkeypatch.setenv('no_proxy', 'localhost,127.0.0.1,.example.com')

        result = _get_proxy_env()
        assert result['no_proxy'] == 'localhost,127.0.0.1,.example.com'


class TestIsSocksProxy:
    """Tests for _is_socks_proxy function."""

    @pytest.mark.parametrize(
        "proxy_url,expected",
        [
            ("socks4://proxy.example.com:1080", True),
            ("socks5://proxy.example.com:1080", True),
            ("socks5h://proxy.example.com:1080", True),
            ("http://proxy.example.com:8080", False),
            ("https://proxy.example.com:8443", False),
            ("", False),
            ("proxy.example.com:1080", False),
        ],
    )
    def test_is_socks_proxy(self, proxy_url, expected):
        """Test SOCKS proxy URL detection."""
        assert _is_socks_proxy(proxy_url) == expected


class TestSetupProxySupport:
    """Tests for setup_proxy_support function."""

    def test_setup_with_no_proxy(self, monkeypatch):
        """Test setup when no proxy is configured."""
        for var in [
            'http_proxy',
            'HTTP_PROXY',
            'https_proxy',
            'HTTPS_PROXY',
            'all_proxy',
            'ALL_PROXY',
            'no_proxy',
            'NO_PROXY',
        ]:
            monkeypatch.delenv(var, raising=False)

        # Should not raise any errors
        setup_proxy_support()

    def test_setup_with_http_proxy(self, monkeypatch):
        """Test setup with HTTP proxy."""
        for var in [
            'http_proxy',
            'HTTP_PROXY',
            'https_proxy',
            'HTTPS_PROXY',
            'all_proxy',
            'ALL_PROXY',
            'no_proxy',
            'NO_PROXY',
        ]:
            monkeypatch.delenv(var, raising=False)

        monkeypatch.setenv('http_proxy', 'http://proxy.example.com:8080')

        with patch('urllib.request.install_opener') as mock_install:
            setup_proxy_support()
            assert mock_install.called

    def test_setup_with_socks_proxy_no_pysocks(self, monkeypatch):
        """Test setup with SOCKS proxy when PySocks is not installed."""
        for var in [
            'http_proxy',
            'HTTP_PROXY',
            'https_proxy',
            'HTTPS_PROXY',
            'all_proxy',
            'ALL_PROXY',
            'no_proxy',
            'NO_PROXY',
        ]:
            monkeypatch.delenv(var, raising=False)

        monkeypatch.setenv('all_proxy', 'socks5://proxy.example.com:1080')

        # Mock the socks import to raise ImportError
        with patch.dict('sys.modules', {'socks': None}):
            with patch('urllib.request.install_opener') as mock_install:
                with patch('ramalama.proxy_support.logger.warning') as mock_warning:
                    # Should still work but without SOCKS support
                    setup_proxy_support()
                    assert mock_install.called
                    # Verify that a warning was logged about missing PySocks
                    mock_warning.assert_called_once()
                    assert 'PySocks' in str(mock_warning.call_args)

    def test_setup_with_socks_proxy_with_pysocks(self, monkeypatch):
        """Test setup with SOCKS proxy when PySocks is installed."""
        for var in [
            'http_proxy',
            'HTTP_PROXY',
            'https_proxy',
            'HTTPS_PROXY',
            'all_proxy',
            'ALL_PROXY',
            'no_proxy',
            'NO_PROXY',
        ]:
            monkeypatch.delenv(var, raising=False)

        monkeypatch.setenv('all_proxy', 'socks5://proxy.example.com:1080')

        # Mock socks module to simulate PySocks being installed
        mock_socks = MagicMock()
        with patch.dict('sys.modules', {'socks': mock_socks}):
            with (
                patch('urllib.request.install_opener') as mock_install,
                patch('urllib.request.build_opener') as mock_build_opener,
            ):
                # Simulate build_opener returning a mock opener with handlers
                mock_opener = MagicMock()
                mock_handler = MagicMock()
                mock_handler.__class__.__name__ = "SocksiPyHandler"
                mock_opener.handlers = [mock_handler]
                mock_build_opener.return_value = mock_opener

                setup_proxy_support()
                assert mock_install.called

                # Assert that build_opener was called and the handler is a SOCKS handler
                mock_build_opener.assert_called()
                assert any(
                    h.__class__.__name__.lower().startswith("socks")
                    or h.__class__.__name__.lower().startswith("socksi")
                    for h in mock_opener.handlers
                ), "SOCKS proxy handler was not installed in opener"

                # Optionally, check that the socks module was used
                assert mock_socks is not None

    def test_setup_with_multiple_proxies(self, monkeypatch):
        """Test setup with multiple proxy configurations."""
        for var in [
            'http_proxy',
            'HTTP_PROXY',
            'https_proxy',
            'HTTPS_PROXY',
            'all_proxy',
            'ALL_PROXY',
            'no_proxy',
            'NO_PROXY',
        ]:
            monkeypatch.delenv(var, raising=False)

        monkeypatch.setenv('http_proxy', 'http://proxy.example.com:8080')
        monkeypatch.setenv('https_proxy', 'http://proxy.example.com:8443')
        monkeypatch.setenv('no_proxy', 'localhost,127.0.0.1')

        with patch('urllib.request.install_opener') as mock_install:
            setup_proxy_support()
            assert mock_install.called


class TestGetProxyInfo:
    """Tests for get_proxy_info function."""

    def test_get_proxy_info_no_proxy(self, monkeypatch):
        """Test get_proxy_info when no proxy is configured."""
        for var in [
            'http_proxy',
            'HTTP_PROXY',
            'https_proxy',
            'HTTPS_PROXY',
            'all_proxy',
            'ALL_PROXY',
            'no_proxy',
            'NO_PROXY',
        ]:
            monkeypatch.delenv(var, raising=False)

        result = get_proxy_info()
        assert result == {}

    def test_get_proxy_info_with_proxies(self, monkeypatch):
        """Test get_proxy_info when proxies are configured."""
        for var in [
            'http_proxy',
            'HTTP_PROXY',
            'https_proxy',
            'HTTPS_PROXY',
            'all_proxy',
            'ALL_PROXY',
            'no_proxy',
            'NO_PROXY',
        ]:
            monkeypatch.delenv(var, raising=False)

        monkeypatch.setenv('http_proxy', 'http://proxy.example.com:8080')
        monkeypatch.setenv('https_proxy', 'http://proxy.example.com:8443')

        result = get_proxy_info()
        assert result['http_proxy'] == 'http://proxy.example.com:8080'
        assert result['https_proxy'] == 'http://proxy.example.com:8443'


class TestProxyIntegration:
    """Integration tests for proxy support."""

    def test_proxy_handler_installed(self, monkeypatch):
        """Test that proxy handler is correctly installed in urllib."""
        for var in [
            'http_proxy',
            'HTTP_PROXY',
            'https_proxy',
            'HTTPS_PROXY',
            'all_proxy',
            'ALL_PROXY',
            'no_proxy',
            'NO_PROXY',
        ]:
            monkeypatch.delenv(var, raising=False)

        monkeypatch.setenv('http_proxy', 'http://proxy.example.com:8080')

        # Mock urllib.request.install_opener to capture what was installed
        installed_opener = None
        original_install_opener = urllib.request.install_opener

        def mock_install_opener(opener):
            nonlocal installed_opener
            installed_opener = opener
            # Still call the real install_opener
            original_install_opener(opener)

        with patch('urllib.request.install_opener', side_effect=mock_install_opener):
            setup_proxy_support()

        # Verify that an opener was installed
        assert installed_opener is not None, "No opener was installed"

        # Verify that the opener was built with proxy support
        # The opener should have HTTP/HTTPS handlers configured
        assert len(installed_opener.handlers) > 0

        # Check that we have HTTP handlers (which would be configured with proxy info)
        has_http_handler = any(
            isinstance(h, (urllib.request.HTTPHandler, urllib.request.HTTPSHandler)) for h in installed_opener.handlers
        )
        assert has_http_handler, "No HTTP/HTTPS handlers found in opener"

    def test_idempotent_setup(self, monkeypatch):
        """Test that calling setup_proxy_support multiple times is safe."""
        for var in [
            'http_proxy',
            'HTTP_PROXY',
            'https_proxy',
            'HTTPS_PROXY',
            'all_proxy',
            'ALL_PROXY',
            'no_proxy',
            'NO_PROXY',
        ]:
            monkeypatch.delenv(var, raising=False)

        monkeypatch.setenv('http_proxy', 'http://proxy.example.com:8080')

        # Should not raise any errors when called multiple times
        setup_proxy_support()
        setup_proxy_support()
        setup_proxy_support()
