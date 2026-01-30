class UnsupportedMessageType(Exception):
    """Raised when a provider request fails or returns an invalid payload."""


class UnsupportedOpenaiMessageType(UnsupportedMessageType):
    """An invalid payload was returned from the OpenAI provider"""


class UnsupportedAnthropicMessageType(UnsupportedMessageType):
    """An invalid payload was returned from the Anthropic provider"""
