import os
import tempfile
from unittest.mock import patch

from ramalama.transports.huggingface import huggingface_endpoint, huggingface_token


def test_huggingface_endpoint_default() -> None:
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("HF_ENDPOINT", None)
        assert huggingface_endpoint() == "https://huggingface.co"


def test_huggingface_endpoint_from_env() -> None:
    with patch.dict(os.environ, {"HF_ENDPOINT": "https://my-mirror.example.com"}):
        assert huggingface_endpoint() == "https://my-mirror.example.com"


def test_huggingface_endpoint_strips_trailing_slash() -> None:
    with patch.dict(os.environ, {"HF_ENDPOINT": "https://my-mirror.example.com/"}):
        assert huggingface_endpoint() == "https://my-mirror.example.com"


def test_huggingface_token_from_env() -> None:
    with patch.dict(os.environ, {"HF_TOKEN": "hf_test_env_token"}):
        assert huggingface_token() == "hf_test_env_token"


def test_huggingface_token_env_takes_precedence_over_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        token_path = os.path.join(tmpdir, "token")
        with open(token_path, "w") as f:
            f.write("hf_file_token\n")
        with (
            patch.dict(os.environ, {"HF_TOKEN": "hf_env_token"}),
            patch("ramalama.transports.huggingface.os.path.expanduser", return_value=token_path),
        ):
            assert huggingface_token() == "hf_env_token"


def test_huggingface_token_from_cached_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        token_path = os.path.join(tmpdir, "token")
        with open(token_path, "w") as f:
            f.write("hf_cached_token\n")
        with (
            patch.dict(os.environ, {}, clear=False),
            patch("ramalama.transports.huggingface.os.path.expanduser", return_value=token_path),
        ):
            os.environ.pop("HF_TOKEN", None)
            assert huggingface_token() == "hf_cached_token"


def test_huggingface_token_file_whitespace_stripped() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        token_path = os.path.join(tmpdir, "token")
        with open(token_path, "w") as f:
            f.write("  hf_whitespace_token  \n")
        with (
            patch.dict(os.environ, {}, clear=False),
            patch("ramalama.transports.huggingface.os.path.expanduser", return_value=token_path),
        ):
            os.environ.pop("HF_TOKEN", None)
            assert huggingface_token() == "hf_whitespace_token"


def test_huggingface_token_empty_env_does_not_fallback_to_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        token_path = os.path.join(tmpdir, "token")
        with open(token_path, "w") as f:
            f.write("hf_file_token\n")
        with (
            patch.dict(os.environ, {"HF_TOKEN": ""}),
            patch("ramalama.transports.huggingface.os.path.expanduser", return_value=token_path),
        ):
            assert huggingface_token() is None


def test_huggingface_token_returns_none_when_no_source() -> None:
    with (
        patch.dict(os.environ, {}, clear=False),
        patch("ramalama.transports.huggingface.os.path.exists", return_value=False),
    ):
        os.environ.pop("HF_TOKEN", None)
        assert huggingface_token() is None


def test_huggingface_token_returns_none_on_file_read_error() -> None:
    with (
        patch.dict(os.environ, {}, clear=False),
        patch("ramalama.transports.huggingface.os.path.exists", return_value=True),
        patch("ramalama.transports.huggingface.os.path.expanduser", return_value="/nonexistent/path/token"),
        patch("builtins.open", side_effect=OSError("permission denied")),
    ):
        os.environ.pop("HF_TOKEN", None)
        assert huggingface_token() is None
