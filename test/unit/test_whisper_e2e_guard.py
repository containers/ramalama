import socket
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from test.e2e.whisper_utils import MODEL, require_model

URLOPEN = "test.e2e.whisper_utils.urllib.request.urlopen"


@pytest.fixture(autouse=True)
def _isolated_hf_env(monkeypatch):
    monkeypatch.setenv("HF_ENDPOINT", "http://hf.invalid")
    monkeypatch.setenv("HF_TOKEN", "")


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("http://hf.invalid/x", code, "err", {}, None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "error, reason",
    [
        (_http_error(404), "HTTP 404"),
        (_http_error(401), "HTTP 401"),
        (_http_error(403), "HTTP 403"),
        (urllib.error.URLError(ConnectionRefusedError()), "ConnectionRefusedError"),
        (urllib.error.URLError(socket.gaierror()), "gaierror"),
        (ConnectionRefusedError(), "ConnectionRefusedError"),
    ],
)
def test_require_model_skips_when_model_unavailable(error, reason):
    with patch(URLOPEN, side_effect=error), pytest.raises(pytest.skip.Exception, match=reason):
        require_model(MODEL)


@pytest.mark.parametrize(
    "error",
    [_http_error(500), _http_error(429), socket.timeout(), urllib.error.URLError(socket.timeout())],
)
def test_require_model_does_not_skip_on_transient_errors(error):
    with patch(URLOPEN, side_effect=error):
        require_model(MODEL)


def test_require_model_runs_test_on_200():
    with patch(URLOPEN, return_value=MagicMock()):
        require_model(MODEL)


def test_require_model_requests_endpoint_url_with_token(monkeypatch):
    monkeypatch.setenv("HF_ENDPOINT", "http://mirror.invalid/")
    monkeypatch.setenv("HF_TOKEN", "tok")
    with patch(URLOPEN, return_value=MagicMock()) as urlopen:
        require_model("huggingface://org/repo/file.bin")
    request = urlopen.call_args.args[0]
    assert urlopen.call_args.kwargs["timeout"] == 10
    assert request.full_url == "http://mirror.invalid/org/repo/raw/main/file.bin"
    assert request.get_header("Authorization") == "Bearer tok"


def test_require_model_sends_no_authorization_without_token(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "")
    with patch(URLOPEN, return_value=MagicMock()) as urlopen:
        require_model(MODEL)
    assert not urlopen.call_args.args[0].has_header("Authorization")
