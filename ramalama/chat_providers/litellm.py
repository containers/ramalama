from __future__ import annotations

from typing import Optional

from ramalama.chat_providers.openai import OpenAICompletionsChatProvider


class LiteLLMChatProvider(OpenAICompletionsChatProvider):
    """Chat provider that routes through a LiteLLM proxy.

    LiteLLM (https://github.com/BerriAI/litellm) is an AI gateway that
    provides a unified OpenAI-compatible endpoint for 100+ LLM providers
    (Anthropic, Bedrock, Vertex, Gemini, Cohere, Mistral, etc.).

    The provider extends OpenAICompletionsChatProvider since the LiteLLM
    proxy speaks the OpenAI Chat Completions format natively.
    """

    provider = "litellm"

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        super().__init__(base_url, api_key)


__all__ = ["LiteLLMChatProvider"]
