"""API key handling shared by the RAG container scripts.

Deliberately free of third-party imports. rag_framework pulls in fastapi,
aiohttp, openai, qdrant_client and uvicorn at module scope, so anything living
in it can only be tested by standing that whole stack up. Keeping the key
handling here instead lets the unit tests import it directly.

Installed next to the scripts in /usr/bin, which is on sys.path for them
because Python puts a script's own directory there.
"""

import secrets


def bearer_header(api_key):
    """Authorization header presenting ``api_key``, empty when there is none."""
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def _header_bytes(value):
    """The bytes a client actually sent in a header.

    Starlette hands header values over latin-1 decoded, which is what HTTP
    specifies, so latin-1 round-trips them back to the wire bytes.
    """
    return value.encode("latin-1", "replace")


def _env_bytes(value):
    """The bytes an environment variable actually held.

    Python decodes the environment as UTF-8 with surrogateescape, so encoding
    it back the same way recovers the bytes ramalama was given.
    """
    return value.encode("utf-8", "surrogateescape")


def is_authorized(api_key, authorization="", x_api_key=""):
    """Whether the presented credentials match ``api_key``.

    An empty ``api_key`` means the endpoint is unauthenticated and everything
    is allowed, which is the default. Otherwise this follows llama.cpp: either
    header form is accepted, and the comparison is constant time so the key
    cannot be recovered by timing the response.

    The comparison is on bytes rather than str. compare_digest raises
    TypeError for a str holding non-ASCII, so a key or a presented token with
    a single accented character would answer 500 instead of 401; comparing
    what each side was decoded from also makes a non-ASCII key actually match.
    """
    if not api_key:
        return True
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        token = x_api_key
    return secrets.compare_digest(_header_bytes(token), _env_bytes(api_key))
