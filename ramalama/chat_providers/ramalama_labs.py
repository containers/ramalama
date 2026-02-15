from ramalama.chat_providers.openai import OpenAICompletionsChatProvider


class RamalamaLabsChatProvider(OpenAICompletionsChatProvider):
    provider: str = "ramalamalabs"
