"""
Unit tests for the 5 commits that improve user experience when a 404 error
is returned by the HuggingFace registry.

Commits covered:
  75f16468 - Raise FileNotFoundError on HTTP 404 in fetch_checksum_from_api_base
  6a520ce8 - Add fetch_gguf_files helper to list GGUF files in a HF repo
  6b7088b0 - Show available GGUF files when a requested file is not found
  742620d9 - Re-raise FileNotFoundError in pull() before CLI fallback
  38731bdf - Clarify get_cli_download_args error message
"""

import io
import tempfile
import urllib.error
import urllib.request
from http.client import HTTPMessage
from unittest.mock import MagicMock, patch

import pytest

from ramalama.hf_style_repo_base import fetch_checksum_from_api_base
from ramalama.transports.huggingface import (
    Huggingface,
    HuggingfaceRepositoryModel,
    fetch_gguf_files,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_http_error(code: int, url: str = "https://huggingface.co/test") -> urllib.error.HTTPError:
    """Return a minimal urllib.error.HTTPError with the given status code."""
    return urllib.error.HTTPError(url, code, f"HTTP Error {code}", HTTPMessage(), None)


def _make_mock_response(body: str) -> MagicMock:
    """Return a context-manager mock whose .read().decode() returns *body*."""
    mock_response = MagicMock()
    mock_response.read.return_value = body.encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


# ===========================================================================
# 1. fetch_checksum_from_api_base — commit 75f16468
# ===========================================================================

class TestFetchChecksumFromApiBase:
    """HTTP 404 must raise FileNotFoundError; other errors must raise KeyError."""

    URL = "https://huggingface.co/org/repo/raw/main/model.gguf"

    def test_404_raises_file_not_found_error(self):
        with patch("urllib.request.urlopen", side_effect=_make_http_error(404, self.URL)):
            with pytest.raises(FileNotFoundError) as exc_info:
                fetch_checksum_from_api_base(self.URL)
        # The URL must appear in the exception so callers can surface it
        assert self.URL in str(exc_info.value)

    def test_non_404_http_error_raises_key_error(self):
        for code in (401, 403, 500, 503):
            with patch("urllib.request.urlopen", side_effect=_make_http_error(code, self.URL)):
                with pytest.raises(KeyError):
                    fetch_checksum_from_api_base(self.URL)

    def test_url_error_raises_key_error(self):
        url_err = urllib.error.URLError("network unreachable")
        with patch("urllib.request.urlopen", side_effect=url_err):
            with pytest.raises(KeyError):
                fetch_checksum_from_api_base(self.URL)

    def test_successful_response_returns_stripped_body(self):
        mock_response = _make_mock_response("  abc123  ")
        with patch("urllib.request.urlopen", return_value=mock_response):
            result = fetch_checksum_from_api_base(self.URL)
        assert result == "abc123"

    def test_extractor_func_is_called_on_success(self):
        mock_response = _make_mock_response("raw data")
        extractor = lambda data: data.upper()
        with patch("urllib.request.urlopen", return_value=mock_response):
            result = fetch_checksum_from_api_base(self.URL, extractor_func=extractor)
        assert result == "RAW DATA"

    def test_404_is_distinct_from_other_http_errors(self):
        """Ensure 404 does NOT raise KeyError (different exception type)."""
        with patch("urllib.request.urlopen", side_effect=_make_http_error(404)):
            with pytest.raises(FileNotFoundError):
                fetch_checksum_from_api_base(self.URL)
        with patch("urllib.request.urlopen", side_effect=_make_http_error(500)):
            with pytest.raises(KeyError):
                fetch_checksum_from_api_base(self.URL)


# ===========================================================================
# 2. fetch_gguf_files — commit 6a520ce8
# ===========================================================================

class TestFetchGgufFiles:
    """fetch_gguf_files must return a sorted list of .gguf paths, ignoring others."""

    REPO = "org/repo"

    def test_returns_only_gguf_files(self):
        files = [
            {"path": "model-q4.gguf", "type": "file"},
            {"path": "README.md", "type": "file"},
            {"path": "config.json", "type": "file"},
        ]
        with patch("ramalama.transports.huggingface.fetch_repo_files", return_value=files):
            result = fetch_gguf_files(self.REPO)
        assert result == ["model-q4.gguf"]

    def test_returns_sorted_list(self):
        files = [
            {"path": "model-q8.gguf", "type": "file"},
            {"path": "model-q4.gguf", "type": "file"},
            {"path": "model-q2.gguf", "type": "file"},
        ]
        with patch("ramalama.transports.huggingface.fetch_repo_files", return_value=files):
            result = fetch_gguf_files(self.REPO)
        assert result == ["model-q2.gguf", "model-q4.gguf", "model-q8.gguf"]

    def test_returns_empty_list_on_exception(self):
        with patch(
            "ramalama.transports.huggingface.fetch_repo_files",
            side_effect=Exception("network error"),
        ):
            result = fetch_gguf_files(self.REPO)
        assert result == []

    def test_returns_empty_list_when_no_gguf_files(self):
        files = [
            {"path": "README.md", "type": "file"},
            {"path": "config.json", "type": "file"},
        ]
        with patch("ramalama.transports.huggingface.fetch_repo_files", return_value=files):
            result = fetch_gguf_files(self.REPO)
        assert result == []

    def test_returns_empty_list_for_empty_repo(self):
        with patch("ramalama.transports.huggingface.fetch_repo_files", return_value=[]):
            result = fetch_gguf_files(self.REPO)
        assert result == []

    def test_ignores_entries_without_path_key(self):
        files = [
            {"name": "no-path.gguf"},          # missing 'path'
            {"path": "valid.gguf"},              # valid
            "not-a-dict",                        # not a dict
        ]
        with patch("ramalama.transports.huggingface.fetch_repo_files", return_value=files):
            result = fetch_gguf_files(self.REPO)
        assert result == ["valid.gguf"]

    def test_passes_revision_to_fetch_repo_files(self):
        with patch(
            "ramalama.transports.huggingface.fetch_repo_files", return_value=[]
        ) as mock_fetch:
            fetch_gguf_files(self.REPO, revision="dev")
        mock_fetch.assert_called_once_with(self.REPO, "dev")


# ===========================================================================
# 3. HuggingfaceRepositoryModel.fetch_metadata — commit 6b7088b0
# ===========================================================================

class TestHuggingfaceRepositoryModelFetchMetadata:
    """fetch_metadata must surface available GGUF files (or a browse URL) on 404."""

    ORG = "myorg/myrepo"
    FILE = "model-q4.gguf"

    def _make_model(self):
        """Instantiate HuggingfaceRepositoryModel with fetch_metadata stubbed out."""
        with patch.object(HuggingfaceRepositoryModel, "fetch_metadata"):
            return HuggingfaceRepositoryModel(self.FILE, self.ORG, "main")

    def test_file_not_found_with_available_gguf_files(self):
        available_files = ["model-q2.gguf", "model-q4.gguf", "model-q8.gguf"]
        model = self._make_model()

        with patch(
            "ramalama.transports.huggingface.fetch_checksum_from_api",
            side_effect=FileNotFoundError("url"),
        ), patch(
            "ramalama.transports.huggingface.fetch_gguf_files",
            return_value=available_files,
        ):
            with pytest.raises(FileNotFoundError) as exc_info:
                model.fetch_metadata()

        msg = str(exc_info.value)
        assert self.FILE in msg
        assert self.ORG in msg
        for f in available_files:
            assert f in msg

    def test_file_not_found_without_available_gguf_files(self):
        model = self._make_model()

        with patch(
            "ramalama.transports.huggingface.fetch_checksum_from_api",
            side_effect=FileNotFoundError("url"),
        ), patch(
            "ramalama.transports.huggingface.fetch_gguf_files",
            return_value=[],
        ):
            with pytest.raises(FileNotFoundError) as exc_info:
                model.fetch_metadata()

        msg = str(exc_info.value)
        assert self.FILE in msg
        assert self.ORG in msg
        # Should include browse URL when no files are available
        assert f"https://huggingface.co/{self.ORG}" in msg

    def test_file_not_found_always_raises_file_not_found_error(self):
        """The re-raised exception must be FileNotFoundError, not KeyError or other."""
        model = self._make_model()

        with patch(
            "ramalama.transports.huggingface.fetch_checksum_from_api",
            side_effect=FileNotFoundError("url"),
        ), patch(
            "ramalama.transports.huggingface.fetch_gguf_files",
            return_value=["a.gguf"],
        ):
            with pytest.raises(FileNotFoundError):
                model.fetch_metadata()

    def test_other_errors_from_fetch_checksum_propagate_unchanged(self):
        """KeyError from fetch_checksum_from_api must not be caught by the 404 handler."""
        model = self._make_model()

        with patch(
            "ramalama.transports.huggingface.fetch_checksum_from_api",
            side_effect=KeyError("auth failure"),
        ):
            with pytest.raises(KeyError):
                model.fetch_metadata()

    def test_success_sets_model_hash_and_filename(self):
        checksum = "abc123def456"
        model = self._make_model()

        with patch(
            "ramalama.transports.huggingface.fetch_checksum_from_api",
            return_value=checksum,
        ), patch(
            "ramalama.transports.huggingface.huggingface_token",
            return_value=None,
        ):
            model.fetch_metadata()

        assert model.model_hash == f"sha256:{checksum}"
        assert model.model_filename == self.FILE


# ===========================================================================
# 4. pull() re-raises FileNotFoundError — commit 742620d9
# ===========================================================================

class TestPullReRaisesFileNotFoundError:
    """FileNotFoundError in pull() must propagate immediately, bypassing CLI fallback."""

    def _make_huggingface(self, tmpdir: str) -> Huggingface:
        return Huggingface("myorg/myrepo/model.gguf", tmpdir)

    def test_file_not_found_propagates_out_of_pull(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hf = self._make_huggingface(tmpdir)

            mock_args = MagicMock()
            mock_args.quiet = True
            mock_args.verify = True
            mock_args.token = None

            # Simulate create_repository raising FileNotFoundError
            with patch.object(
                hf,
                "create_repository",
                side_effect=FileNotFoundError("model.gguf not found"),
            ), patch.object(
                hf.model_store,
                "get_cached_files",
                return_value=("hash", [], False),
            ):
                with pytest.raises(FileNotFoundError):
                    hf.pull(mock_args)

    def test_file_not_found_does_not_trigger_cli_fallback(self):
        """get_cli_download_args must NOT be called when FileNotFoundError is raised."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hf = self._make_huggingface(tmpdir)

            mock_args = MagicMock()
            mock_args.quiet = True
            mock_args.verify = True
            mock_args.token = None

            with patch.object(
                hf,
                "create_repository",
                side_effect=FileNotFoundError("model.gguf not found"),
            ), patch.object(
                hf.model_store,
                "get_cached_files",
                return_value=("hash", [], False),
            ), patch.object(
                hf, "get_cli_download_args"
            ) as mock_cli:
                with pytest.raises(FileNotFoundError):
                    hf.pull(mock_args)

            mock_cli.assert_not_called()

    def test_generic_exception_still_attempts_cli_fallback(self):
        """A non-FileNotFoundError exception should attempt the CLI fallback path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hf = self._make_huggingface(tmpdir)

            mock_args = MagicMock()
            mock_args.quiet = True
            mock_args.verify = True
            mock_args.token = None

            # Patch available() to return False so it raises KeyError instead of running CLI
            with patch.object(
                hf,
                "create_repository",
                side_effect=RuntimeError("some transient error"),
            ), patch.object(
                hf.model_store,
                "get_cached_files",
                return_value=("hash", [], False),
            ), patch(
                "ramalama.hf_style_repo_base.available", return_value=False
            ):
                with pytest.raises(KeyError):
                    hf.pull(mock_args)


# ===========================================================================
# 5. get_cli_download_args — commit 38731bdf
# ===========================================================================

class TestGetCliDownloadArgs:
    """get_cli_download_args must raise NotImplementedError with the updated message."""

    def test_raises_not_implemented_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hf = Huggingface("myorg/myrepo/model.gguf", tmpdir)
            with pytest.raises(NotImplementedError):
                hf.get_cli_download_args("/tmp/dir", "myorg/myrepo/model.gguf")

    def test_error_message_mentions_cli_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hf = Huggingface("myorg/myrepo/model.gguf", tmpdir)
            with pytest.raises(NotImplementedError) as exc_info:
                hf.get_cli_download_args("/tmp/dir", "myorg/myrepo/model.gguf")
        msg = str(exc_info.value)
        assert "CLI fallback" in msg or "not supported" in msg.lower()

    def test_error_message_does_not_say_not_available(self):
        """Old message said 'huggingface cli download not available'; verify it's gone."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hf = Huggingface("myorg/myrepo/model.gguf", tmpdir)
            with pytest.raises(NotImplementedError) as exc_info:
                hf.get_cli_download_args("/tmp/dir", "myorg/myrepo/model.gguf")
        # The old misleading message fragment must no longer appear
        assert "huggingface cli download not available" not in str(exc_info.value).lower()
