import socket
import urllib.error
import urllib.request
import wave

import pytest

from ramalama.transports.huggingface import huggingface_endpoint, huggingface_token

MODEL = "huggingface://ggerganov/whisper.cpp/ggml-tiny.en.bin"
WHISPER_IMAGE = "ghcr.io/ggml-org/whisper.cpp"

_MODEL_MISSING_CODES = (401, 403, 404)


def _network_available() -> bool:
    try:
        with socket.create_connection(("huggingface.co", 443), timeout=3):
            return True
    except OSError:
        return False


def _require_network() -> None:
    if not _network_available():
        pytest.skip("no network access to resolve the whisper.cpp model")


def require_model(model_uri: str) -> None:
    """Skip the calling test when the configured Hugging Face endpoint cannot serve the model.

    Sends the same first request a pull makes (raw file metadata). Timeouts, 429 and 5xx
    do not skip: they are transient and the test should surface them.
    """
    org, repo, filename = model_uri.split("://", 1)[1].split("/", 2)
    endpoint = huggingface_endpoint()
    headers = {}
    token = huggingface_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"{endpoint}/{org}/{repo}/raw/main/{filename}", headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=10):
            return
    except urllib.error.HTTPError as exc:
        if exc.code in _MODEL_MISSING_CODES:
            pytest.skip(f"whisper model {filename} not available from {endpoint} (HTTP {exc.code})")
    except urllib.error.URLError as exc:
        _skip_if_unreachable(exc.reason, filename, endpoint)
    except OSError as exc:  # socket errors urllib did not wrap in URLError
        _skip_if_unreachable(exc, filename, endpoint)


def _skip_if_unreachable(cause: object, filename: str, endpoint: str) -> None:
    if isinstance(cause, (ConnectionRefusedError, socket.gaierror)):
        pytest.skip(f"whisper model {filename} not available from {endpoint} ({type(cause).__name__})")


def _write_silence(path, seconds: float = 1.0) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * int(16000 * seconds))
