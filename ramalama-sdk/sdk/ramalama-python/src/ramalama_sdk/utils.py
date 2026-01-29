import json
import urllib.request
from datetime import datetime
from typing import TYPE_CHECKING

from ramalama_sdk.schemas import ChatMessage, ModelRecord

from ramalama.model_store.global_store import GlobalModelStore

if TYPE_CHECKING:
    from ramalama_sdk.main import RamalamaModelBase


def is_server_healthy(port: int | str) -> bool:
    """Check whether the local server health endpoint is responding.

    Args:
        port: Port for the local server.

    Returns:
        True if the server responds with HTTP 200.
    """
    url = f"http://localhost:{port}/health"
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=1) as response:
        return response.status == 200


def list_models(store: GlobalModelStore, engine: str) -> list[ModelRecord]:
    """List locally available models, sorted by last modified time."""
    models = store.list_models(engine=engine, show_container=True)
    local_tz = datetime.now().astimezone().tzinfo

    ret = []
    for model, files in models.items():
        is_partial = False
        size = 0
        last_modified = 0
        for f in files:
            if f.is_partial:
                is_partial = True
                break

            size += f.size
            last_modified = max(last_modified, f.modified)

        if not is_partial:
            model = ModelRecord(
                name=model,
                size=size,
                last_modified=datetime.fromtimestamp(last_modified, tz=local_tz),
            )

            ret.append(model)

    ret.sort(key=lambda m: m.last_modified, reverse=True)
    return ret


def make_chat_request(
    model: "RamalamaModelBase", message: str, history: list[ChatMessage] | None = None
) -> ChatMessage:
    """Send a synchronous chat completion request to the running server.

    Args:
        model: Active model instance with a running server.
        message: User prompt content.
        history: Optional prior conversation messages.

    Returns:
        Assistant message payload.

    Raises:
        RuntimeError: If the server is not running.
    """
    if not model.server_attributes.open:
        raise RuntimeError("Server is not running. Call serve() first.")

    messages: list[ChatMessage] = list(history) if history else []
    messages.append({"role": "user", "content": message})

    data: dict = {
        "model": model.model_name,
        "messages": messages,
        "stream": False,
    }
    if model.args.temp:
        data["temperature"] = float(model.args.temp)
    if model.args.max_tokens:
        data["max_completion_tokens"] = model.args.max_tokens

    url = f"{model.server_attributes.url}/chat/completions"
    headers = {"Content-Type": "application/json"}
    request = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    response = urllib.request.urlopen(request)
    response = json.loads(response.read())

    result = ChatMessage(role="assistant", content=response["choices"][0]["message"]["content"])
    return result
