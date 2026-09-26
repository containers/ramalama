from __future__ import annotations

import json
from typing import Any, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlparse

from ramalama.chat_providers.base import ChatProviderError
from ramalama.chat_providers.openai import OpenAICompletionsChatProvider
from ramalama.plugins.runtimes.inference.llama_cpp import parse_models_payload


class ModelServerError(Exception):
    """Raised when a model server request fails or returns an invalid payload."""


def _get_url_origin(url: str) -> tuple[str, str, Optional[int]]:
    """Return the scheme, hostname, and effective port for a URL."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()

    if parsed.port is not None:
        port = parsed.port
    elif scheme == "https":
        port = 443
    elif scheme == "http":
        port = 80
    else:
        port = None

    return scheme, hostname, port


class ModelServerRedirectHandler(urllib_request.HTTPRedirectHandler):
    """Reject model-server redirects that change origin."""

    def __init__(self, origin_url: str):
        self._origin = _get_url_origin(origin_url)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if _get_url_origin(newurl) != self._origin:
            raise urllib_error.HTTPError(
                req.full_url,
                code,
                "Unsafe redirect blocked",
                headers,
                fp,
            )

        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _build_model_server_opener(url: str) -> urllib_request.OpenerDirector:
    """Build an opener that only follows same-origin redirects."""
    return urllib_request.build_opener(ModelServerRedirectHandler(url))


def normalize_server_url(url: str) -> tuple[str, str]:
    """Return (server_root, openai_base) for the given server URL."""
    url = url.rstrip("/")
    if url.endswith("/v1"):
        return url[:-3], url
    return url, f"{url}/v1"


def _fetch_json(
    url: str,
    api_key: Optional[str] = None,
    opener: Optional[urllib_request.OpenerDirector] = None,
) -> tuple[int, Any]:
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = urllib_request.Request(url, headers=headers, method="GET")
    try:
        open_request = opener.open if opener is not None else urllib_request.urlopen
        with open_request(request, timeout=10) as response:
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

    provider = OpenAICompletionsChatProvider(openai_base, api_key)
    opener = _build_model_server_opener(server_root) if provider.api_key else None

    try:
        return provider.list_models(opener=opener)
    except ChatProviderError as exc:
        if exc.status_code in (401, 403):
            raise ModelServerError(
                "Could not authenticate with the model server. Set RAMALAMA_API_KEY or pass --api-key."
            ) from exc
    except urllib_error.HTTPError:
        pass
    except urllib_error.URLError as exc:
        raise ModelServerError(f"Could not connect to model server at {server_root}: {exc.reason}") from exc

    fallback_opener = _build_model_server_opener(server_root) if api_key else None
    status, payload = _fetch_json(
        f"{server_root}/models",
        api_key,
        opener=fallback_opener,
    )
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
