import logging
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ramalama.http_client import HttpClient, TruncatedDownloadError, download_file


@pytest.fixture(autouse=True)
def _ensure_logger_propagation():
    """Ensure the ramalama logger propagates so caplog can capture records."""
    log = logging.getLogger("ramalama")
    orig = log.propagate
    log.propagate = True
    yield
    log.propagate = orig


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


class _TruncatingHandler(BaseHTTPRequestHandler):
    """Serves bodies that are deliberately shorter than the Content-Length they declare.

    The default HTTP/1.0 protocol_version closes the connection once the handler returns,
    which is what makes the short body reach the client as a plain EOF.
    """

    BODY = bytes(range(256)) * 4  # 1024 bytes
    TRUNCATED_AT = 100

    def log_message(self, format, *args):  # noqa: A002 - signature fixed by BaseHTTPRequestHandler
        pass

    def do_GET(self):
        if self.path == "/truncated":
            self.send_response(200)
            self.send_header("Content-Length", str(len(self.BODY)))
            self.end_headers()
            self.wfile.write(self.BODY[: self.TRUNCATED_AT])
        elif self.path == "/complete":
            self.send_response(200)
            self.send_header("Content-Length", str(len(self.BODY)))
            self.end_headers()
            self.wfile.write(self.BODY)
        elif self.path == "/nolength":
            # No Content-Length at all: the body is delimited by the connection close.
            self.send_response(200)
            self.end_headers()
            self.wfile.write(self.BODY)
        elif self.path == "/ignoresrange":
            # Answers 200 with the whole body even though the client asked for a range.
            self.send_response(200)
            self.send_header("Content-Length", str(len(self.BODY)))
            self.end_headers()
            self.wfile.write(self.BODY)
        elif self.path == "/badrange":
            # Answers 206, but starts the body somewhere other than where the client asked.
            start = 500
            remaining = self.BODY[start:]
            self.send_response(206)
            self.send_header("Content-Length", str(len(remaining)))
            self.send_header("Content-Range", f"bytes {start}-{len(self.BODY) - 1}/{len(self.BODY)}")
            self.end_headers()
            self.wfile.write(remaining)
        elif self.path == "/resumable":
            # Truncate the first attempt, then honour the Range header the client sends
            # on the retry so the download can resume instead of restarting.
            start = 0
            range_header = self.headers.get("Range", "")
            match = re.match(r"bytes=(\d+)-", range_header)
            if match:
                start = int(match.group(1))

            self.server.request_count += 1
            if self.server.request_count == 1:
                self.send_response(200)
                self.send_header("Content-Length", str(len(self.BODY)))
                self.end_headers()
                self.wfile.write(self.BODY[: self.TRUNCATED_AT])
            else:
                remaining = self.BODY[start:]
                self.send_response(206)
                self.send_header("Content-Length", str(len(remaining)))
                self.send_header("Content-Range", f"bytes {start}-{len(self.BODY) - 1}/{len(self.BODY)}")
                self.end_headers()
                self.wfile.write(remaining)
        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture
def truncating_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _TruncatingHandler)
    server.request_count = 0
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TestTruncatedDownload:
    def test_truncated_body_raises(self, truncating_server, tmp_path):
        dest = tmp_path / "model.gguf"

        with pytest.raises(TruncatedDownloadError) as excinfo:
            HttpClient().init(
                url=f"{truncating_server}/truncated",
                headers={},
                output_file=str(dest),
                show_progress=False,
            )

        assert "100 of 1024 bytes" in str(excinfo.value)
        # The short body must not be promoted to the real path ...
        assert not dest.exists()
        # ... and the bytes we did get stay in the partial so the retry can resume.
        partial = tmp_path / "model.gguf.partial"
        assert partial.read_bytes() == _TruncatingHandler.BODY[:100]

    def test_truncated_download_error_is_retried_by_download_file(self):
        # download_file's existing IOError arm is what makes the retry loop resume.
        assert issubclass(TruncatedDownloadError, IOError)

    def test_complete_body_renames(self, truncating_server, tmp_path):
        dest = tmp_path / "model.gguf"

        HttpClient().init(
            url=f"{truncating_server}/complete",
            headers={},
            output_file=str(dest),
            show_progress=False,
        )

        assert dest.read_bytes() == _TruncatingHandler.BODY
        assert not (tmp_path / "model.gguf.partial").exists()

    def test_missing_content_length_not_treated_as_truncated(self, truncating_server, tmp_path):
        dest = tmp_path / "model.gguf"

        HttpClient().init(
            url=f"{truncating_server}/nolength",
            headers={},
            output_file=str(dest),
            show_progress=False,
        )

        assert dest.read_bytes() == _TruncatingHandler.BODY

    def test_range_ignored_by_server_restarts_instead_of_appending(self, truncating_server, tmp_path):
        dest = tmp_path / "model.gguf"
        partial = tmp_path / "model.gguf.partial"
        partial.write_bytes(b"\x00" * 100)  # left behind by an earlier, interrupted attempt

        HttpClient().init(
            url=f"{truncating_server}/ignoresrange",
            headers={},
            output_file=str(dest),
            show_progress=False,
        )

        # A 200 reply carries the whole body from byte 0. Appending it to the stale partial
        # would leave a file 100 bytes too long, and the size check would not catch it.
        assert dest.read_bytes() == _TruncatingHandler.BODY
        assert not partial.exists()

    def test_mismatched_range_start_is_rejected(self, truncating_server, tmp_path):
        dest = tmp_path / "model.gguf"
        partial = tmp_path / "model.gguf.partial"
        partial.write_bytes(b"\x00" * 100)  # left behind by an earlier, interrupted attempt

        # The 206 body starts at byte 500, not at the 100 bytes already on disk, so it can
        # neither be appended nor written from byte 0.
        with pytest.raises(IOError, match="unusable"):
            HttpClient().init(
                url=f"{truncating_server}/badrange",
                headers={},
                output_file=str(dest),
                show_progress=False,
            )

        assert not dest.exists()
        # The stale partial is gone, so the retry asks for the whole file again.
        assert not partial.exists()

    def test_mismatched_range_start_is_rejected_from_byte_zero(self, truncating_server, tmp_path):
        dest = tmp_path / "model.gguf"

        # Nothing has been downloaded yet, so the client asks for "bytes=0-". The 206 body
        # still starts at byte 500, and writing it from byte 0 would leave a file that is
        # the right length but the wrong content, which the size check cannot catch.
        with pytest.raises(IOError, match="unusable"):
            HttpClient().init(
                url=f"{truncating_server}/badrange",
                headers={},
                output_file=str(dest),
                show_progress=False,
            )

        assert not dest.exists()
        assert not (tmp_path / "model.gguf.partial").exists()

    def test_download_file_rejects_a_persistently_bad_range(self, truncating_server, tmp_path):
        dest = tmp_path / "model.gguf"
        config = SimpleNamespace(http_client=SimpleNamespace(max_retries=2, max_retry_delay=0))

        # /badrange answers every attempt the same way, so the retry loop has to give up
        # rather than promote the mismatched body to the real path.
        with patch("ramalama.http_client.ActiveConfig", return_value=config):
            with pytest.raises(ConnectionError):
                download_file(url=f"{truncating_server}/badrange", dest_path=str(dest), show_progress=False)

        assert not dest.exists()
        assert not (tmp_path / "model.gguf.partial").exists()

    def test_download_file_resumes_after_truncation(self, truncating_server, tmp_path):
        dest = tmp_path / "model.gguf"

        download_file(url=f"{truncating_server}/resumable", dest_path=str(dest), show_progress=False)

        assert dest.read_bytes() == _TruncatingHandler.BODY
        assert not (tmp_path / "model.gguf.partial").exists()
