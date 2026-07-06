from __future__ import annotations

import json
from typing import Any, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

from ramalama.chat_providers.base import ChatProviderError
from ramalama.chat_providers.openai import OpenAICompletionsChatProvider
from ramalama.plugins.runtimes.inference.llama_cpp import parse_models_payload


class ModelServerError(Exception):
    """Raised when a model server request fails or returns an invalid payload."""


def normalize_server_url(url: str) -> tuple[str, str]:
    """Return (server_root, openai_base) for the given server URL."""
    url = url.rstrip("/")
    if url.endswith("/v1"):
        return url[:-3], url
    return url, f"{url}/v1"


def _fetch_json(url: str, api_key: Optional[str] = None) -> tuple[int, Any]:
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = urllib_request.Request(url, headers=headers, method="GET")
    try:
        with urllib_request.urlopen(request, timeout=10) as response:
            body = response.read()
            if not body:
                return response.status, {}
            try:
                return response.status, json.loads(body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ModelServerError(f"Invalid JSON response from model server at {url}") from exc
    except urllib_error.HTTPError as exc:
        payload: Any = {}
        if exc.fp:
            try:
                payload = json.loads(exc.read().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = {}
        return exc.code, payload
    except urllib_error.URLError as exc:
        raise ModelServerError(f"Could not connect to model server at {url}: {exc.reason}") from exc


def list_server_models(url: str, api_key: Optional[str] = None) -> list[str]:
    """Return model identifiers exposed by a running inference server."""
    server_root, openai_base = normalize_server_url(url)

    try:
        return OpenAICompletionsChatProvider(openai_base, api_key).list_models()
    except ChatProviderError as exc:
        if exc.status_code in (401, 403):
            raise ModelServerError(
                "Could not authenticate with the model server. Set RAMALAMA_API_KEY or pass --api-key."
            ) from exc
    except urllib_error.HTTPError:
        pass
    except urllib_error.URLError as exc:
        raise ModelServerError(f"Could not connect to model server at {server_root}: {exc.reason}") from exc

    status, payload = _fetch_json(f"{server_root}/models", api_key)
    if status == 200:
        try:
            return parse_models_payload(payload)
        except ValueError as exc:
            raise ModelServerError("Invalid model list payload from llama.cpp /models endpoint") from exc

    if status in (401, 403):
        raise ModelServerError("Could not authenticate with the model server. Set RAMALAMA_API_KEY or pass --api-key.")

    raise ModelServerError(
        f"Could not list models from {server_root}. Tried /v1/models and /models; last response status was {status}."
    )
