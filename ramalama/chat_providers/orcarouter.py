from __future__ import annotations

from typing import Optional

from ramalama.chat_providers.openai import OpenAICompletionsChatProvider

ORCAROUTER_DEFAULT_BASE_URL: str = "https://api.orcarouter.ai/v1"
ORCAROUTER_DEFAULT_MODEL: str = "orcarouter/auto"


class OrcaRouterChatProvider(OpenAICompletionsChatProvider):
    """Chat provider for the OrcaRouter OpenAI-compatible gateway.

    OrcaRouter routes chat completions to upstream models selected by the model
    identifier (e.g. ``orcarouter/auto`` for the smart router). It is a
    chat-only gateway; embeddings and other non-chat endpoints are not exposed.
    """

    provider = "orcarouter"
    default_path = "/chat/completions"

    def __init__(self, base_url: str = ORCAROUTER_DEFAULT_BASE_URL, api_key: Optional[str] = None):
        super().__init__(base_url, api_key)


__all__ = ["OrcaRouterChatProvider", "ORCAROUTER_DEFAULT_BASE_URL", "ORCAROUTER_DEFAULT_MODEL"]
