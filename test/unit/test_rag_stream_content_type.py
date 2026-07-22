import asyncio
import importlib
import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# The RAG proxy is a standalone container script (no ``.py`` extension) that
# imports a handful of packages which are only installed inside the RAG
# container image, not in the unit-test environment.  We stub the ones that
# are missing so the module can be imported and its response-construction
# logic exercised in isolation.
RAG_FRAMEWORK = Path(__file__).resolve().parents[2] / "container-images" / "scripts" / "rag_framework"


def _stub_pydantic():
    module = type(sys)("pydantic")

    class BaseModel:  # minimal stand-in; models are never instantiated here
        pass

    def Field(default=None, *args, **kwargs):
        return default

    module.BaseModel = BaseModel
    module.Field = Field
    return module


def _stub_fastapi():
    module = type(sys)("fastapi")

    class _App:
        def __init__(self, *args, **kwargs):
            pass

        def _decorator(self, *args, **kwargs):
            def wrap(func):
                return func

            return wrap

        get = post = put = delete = middleware = _decorator

    class HTTPException(Exception):
        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("detail", ""))

    module.FastAPI = lambda *a, **k: _App()
    module.HTTPException = HTTPException
    return module


def _stub_fastapi_responses():
    module = type(sys)("fastapi.responses")

    class StreamingResponse:
        def __init__(self, content, media_type=None, headers=None, **kwargs):
            self.body_iterator = content
            self.media_type = media_type
            self.headers = headers or {}

    module.StreamingResponse = StreamingResponse
    return module


def _load_rag_framework():
    # Optional heavy deps that only ship in the container image.
    for name in ("aiohttp", "openai", "qdrant_client", "uvicorn"):
        if name not in sys.modules:
            try:
                importlib.import_module(name)
            except ImportError:
                sys.modules[name] = MagicMock()

    if "pydantic" not in sys.modules:
        try:
            importlib.import_module("pydantic")
        except ImportError:
            sys.modules["pydantic"] = _stub_pydantic()

    try:
        importlib.import_module("fastapi")
        importlib.import_module("fastapi.responses")
    except ImportError:
        sys.modules["fastapi"] = _stub_fastapi()
        sys.modules["fastapi.responses"] = _stub_fastapi_responses()

    loader = SourceFileLoader("ramalama_rag_framework", str(RAG_FRAMEWORK))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_stream_completion_uses_sse_media_type():
    """Regression test for #2837: streaming chat completions must advertise
    ``text/event-stream`` so strict OpenAI clients (e.g. Open WebUI) accept
    the SSE body instead of rejecting it as ``text/plain``."""
    rag_framework = _load_rag_framework()

    # Bypass __init__: it would try to open Qdrant/OpenAI clients.  The
    # streaming generator is not iterated, so ``self`` is never dereferenced.
    service = rag_framework.RagService.__new__(rag_framework.RagService)

    response = asyncio.run(service._stream_completion("cmpl-id", 0, MagicMock(), []))

    assert response.media_type == "text/event-stream"
    # SSE responses must not be cached.
    headers = {key.lower(): value for key, value in dict(response.headers).items()}
    assert headers.get("cache-control") == "no-cache"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
