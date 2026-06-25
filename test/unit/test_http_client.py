import logging
from unittest.mock import MagicMock, patch

from ramalama.http_client import HttpClient


class TestUrlopenHeaderMasking:
    def test_authorization_header_masked_in_debug_log(self, caplog):
        client = HttpClient()
        client.file_size = 0
        headers = {
            "Authorization": "Bearer hf_secrettoken123",
            "Accept": "application/octet-stream",
        }

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.getheader.return_value = "1024"

        with patch("urllib.request.urlopen", return_value=mock_response):
            with caplog.at_level(logging.DEBUG, logger="ramalama"):
                client.urlopen("https://example.com/model.gguf", headers)

        debug_messages = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
        log_line = next((m for m in debug_messages if "Running urlopen" in m), None)
        assert log_line is not None, "Expected 'Running urlopen' in debug log output"

        assert "hf_secrettoken123" not in log_line
        assert "****" in log_line
        assert "application/octet-stream" in log_line

    def test_no_authorization_header_logged_normally(self, caplog):
        client = HttpClient()
        client.file_size = 0
        headers = {"Accept": "application/octet-stream"}

        mock_response = MagicMock()
        mock_response.status = 200

        with patch("urllib.request.urlopen", return_value=mock_response):
            with caplog.at_level(logging.DEBUG, logger="ramalama"):
                client.urlopen("https://example.com/model.gguf", headers)

        debug_messages = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
        log_line = next((m for m in debug_messages if "Running urlopen" in m), None)
        assert log_line is not None, "Expected 'Running urlopen' in debug log output"

        assert "****" not in log_line
        assert "application/octet-stream" in log_line

    def test_authorization_header_masked_case_insensitive(self, caplog):
        client = HttpClient()
        client.file_size = 0
        headers = {"authorization": "Bearer hf_secrettoken123"}

        mock_response = MagicMock()
        mock_response.status = 200

        with patch("urllib.request.urlopen", return_value=mock_response):
            with caplog.at_level(logging.DEBUG, logger="ramalama"):
                client.urlopen("https://example.com/model.gguf", headers)

        debug_messages = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
        log_line = next((m for m in debug_messages if "Running urlopen" in m), None)
        assert log_line is not None, "Expected 'Running urlopen' in debug log output"

        assert "hf_secrettoken123" not in log_line
        assert "****" in log_line

    def test_authorization_header_still_sent_in_request(self):
        client = HttpClient()
        client.file_size = 0
        token = "Bearer hf_secrettoken123"
        headers = {"Authorization": token}

        mock_response = MagicMock()
        mock_response.status = 200

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            client.urlopen("https://example.com/model.gguf", headers)

        request = mock_urlopen.call_args[0][0]
        assert request.get_header("Authorization") == token
