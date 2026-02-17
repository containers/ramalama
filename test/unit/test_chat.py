from argparse import Namespace
from unittest.mock import Mock, patch

import pytest

from ramalama.chat import wait_for_server

@patch("ramalama.chat.Spinner")
@patch("ramalama.chat.HTTPConnection")
def test_wait_for_server_success(mock_conn, mock_spinner):
    mock_resp = Mock()
    mock_resp.status = 200
    mock_resp.read.return_value = b""
    mock_conn.return_value.getresponse.return_value = mock_resp
    args = Namespace(url="http://127.0.0.1:8080/v1")
    wait_for_server(args, timeout=30)
    assert mock_conn.return_value.request.called

@patch("ramalama.chat.Spinner")
@patch("ramalama.chat.time.sleep")
@patch("ramalama.chat.HTTPConnection")
def test_wait_for_server_timeout(mock_conn, mock_sleep, mock_spinner):
    mock_resp = Mock()
    mock_resp.status = 503
    mock_resp.read.return_value = b""
    mock_conn.return_value.getresponse.return_value = mock_resp
    args = Namespace(url="http://127.0.0.1:8080/v1")
    wait_for_server(args, timeout=0)

@patch("ramalama.chat.Spinner")
@patch("ramalama.chat.time.sleep")
@patch("ramalama.chat.HTTPConnection")
def test_wait_for_server_retry_success(mock_conn, mock_sleep, mock_spinner):
    mock_resp_fail = Mock()
    mock_resp_fail.status = 503
    mock_resp_fail.read.return_value = b""
    mock_resp_success = Mock()
    mock_resp_success.status = 200
    mock_resp_success.read.return_value = b""
    mock_conn.return_value.getresponse.side_effect = [mock_resp_fail, mock_resp_success]
    args = Namespace(url="http://127.0.0.1:8080/v1")
    wait_for_server(args, timeout=30)
    assert mock_conn.return_value.getresponse.call_count == 2    