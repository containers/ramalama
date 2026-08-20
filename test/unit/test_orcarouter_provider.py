from ramalama.chat_providers.base import ChatRequestOptions
from ramalama.chat_providers.orcarouter import (
    ORCAROUTER_DEFAULT_BASE_URL,
    ORCAROUTER_DEFAULT_MODEL,
    OrcaRouterChatProvider,
)
from ramalama.chat_utils import UserMessage


def test_defaults():
    provider = OrcaRouterChatProvider()

    assert provider.provider == "orcarouter"
    assert provider.base_url == "https://api.orcarouter.ai/v1"
    assert ORCAROUTER_DEFAULT_MODEL == "orcarouter/auto"


def test_custom_base_url_and_api_key():
    provider = OrcaRouterChatProvider(base_url="https://api.orcarouter.ai/v1", api_key="sk-orca-test")

    assert provider.base_url == "https://api.orcarouter.ai/v1"
    assert provider.api_key == "sk-orca-test"


def test_default_path():
    provider = OrcaRouterChatProvider()

    assert provider.default_path == "/chat/completions"


def test_build_url_includes_default_path():
    provider = OrcaRouterChatProvider()

    assert provider.build_url() == f"{ORCAROUTER_DEFAULT_BASE_URL}/chat/completions"


def test_completions_payload():
    provider = OrcaRouterChatProvider()
    options = ChatRequestOptions(model=ORCAROUTER_DEFAULT_MODEL, stream=False)
    payload = provider.build_payload([UserMessage(text="hello")], options)

    assert payload["model"] == "orcarouter/auto"
    assert payload["stream"] is False
    assert payload["messages"] == [{"role": "user", "content": "hello"}]


def test_auth_headers_bearer():
    provider = OrcaRouterChatProvider(api_key="sk-orca-test")

    assert provider.auth_headers() == {"Authorization": "Bearer sk-orca-test"}


def test_list_models_url():
    provider = OrcaRouterChatProvider()

    assert provider.build_url("/models") == f"{ORCAROUTER_DEFAULT_BASE_URL}/models"
