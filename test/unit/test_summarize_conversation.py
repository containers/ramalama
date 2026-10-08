import json
import urllib.error
import urllib.request
from unittest.mock import MagicMock

import pytest

from ramalama.chat import RamaLamaShell
from ramalama.chat_utils import AssistantMessage, SystemMessage, UserMessage


def make_shell(summarize_after=4):
    args = MagicMock()
    args.prefix = "> "
    args.url = "http://localhost:8080"
    args.model = "test-model"
    args.rag = None
    args.mcp = []
    args.summarize_after = summarize_after
    args.color = "never"
    shell = RamaLamaShell(args)
    shell._make_api_request = MagicMock()
    return shell


@pytest.fixture
def shell():
    return make_shell()


def mock_summary_response(summary_text):
    response_data = json.dumps({"choices": [{"message": {"content": summary_text}}]}).encode()
    mock_response = MagicMock()
    mock_response.read.return_value = response_data
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


def make_history(*pairs):
    """Build conversation history from (user, assistant) string pairs."""
    history = []
    for user_text, asst_text in pairs:
        history.append(UserMessage(text=user_text))
        history.append(AssistantMessage(text=asst_text))
    return history


def test_summarize_disabled_when_summarize_after_zero():
    sh = make_shell(summarize_after=0)
    sh.conversation_history = make_history(("hi", "hello"), ("foo", "bar"), ("baz", "qux"))
    original = list(sh.conversation_history)
    sh._check_and_summarize()
    assert sh.conversation_history == original


def test_summarize_skipped_when_not_enough_messages(shell):
    shell.conversation_history = make_history(("hi", "hello"))
    original = list(shell.conversation_history)
    shell._check_and_summarize()
    assert shell.conversation_history == original


def test_summarize_proceeds_when_enough_messages(shell, monkeypatch):
    shell.conversation_history = make_history(("a", "b"), ("c", "d"), ("e", "f"))
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: mock_summary_response("summary"))
    shell._summarize_conversation()
    assert any(isinstance(m, SystemMessage) and "summary" in m.text for m in shell.conversation_history)


def test_summarize_no_rag_preserves_recent_two_messages(shell, monkeypatch):
    history = make_history(("a", "b"), ("c", "d"), ("e", "f"))
    shell.conversation_history = list(history)
    recent_user = history[-2]
    recent_asst = history[-1]
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: mock_summary_response("the summary"))
    shell._summarize_conversation()
    assert shell.conversation_history[-2] is recent_user
    assert shell.conversation_history[-1] is recent_asst


def test_summarize_no_rag_inserts_summary_system_message(shell, monkeypatch):
    shell.conversation_history = make_history(("a", "b"), ("c", "d"), ("e", "f"))
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: mock_summary_response("the summary"))
    shell._summarize_conversation()
    summary_msgs = [m for m in shell.conversation_history if isinstance(m, SystemMessage)]
    assert len(summary_msgs) == 1
    assert "the summary" in summary_msgs[0].text


def test_summarize_preserves_single_rag_message(shell, monkeypatch):
    rag_msg = UserMessage(text="rag context")
    shell.conversation_history = [rag_msg] + make_history(("a", "b"), ("c", "d"), ("e", "f"))
    shell.rag_prefix_len = 1
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: mock_summary_response("summary"))
    shell._summarize_conversation()
    assert shell.conversation_history[0] is rag_msg


def test_summarize_preserves_double_rag_messages(shell, monkeypatch):
    rag_text = UserMessage(text="rag text")
    rag_image = UserMessage(text="rag image")
    shell.conversation_history = [rag_text, rag_image] + make_history(("a", "b"), ("c", "d"), ("e", "f"))
    shell.rag_prefix_len = 2
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: mock_summary_response("summary"))
    shell._summarize_conversation()
    assert shell.conversation_history[0] is rag_text
    assert shell.conversation_history[1] is rag_image


def test_summarize_double_rag_not_included_in_summarized_messages(shell, monkeypatch):
    rag_text = UserMessage(text="rag text")
    rag_image = UserMessage(text="rag image")
    exchanges = make_history(("a", "b"), ("c", "d"), ("e", "f"))
    shell.conversation_history = [rag_text, rag_image] + exchanges
    shell.rag_prefix_len = 2

    captured_prompt = {}

    def capture_request(messages, **kwargs):
        captured_prompt["messages"] = messages
        return MagicMock()

    shell._make_api_request = capture_request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: mock_summary_response("summary"))
    shell._summarize_conversation()

    prompt_text = captured_prompt["messages"][0].text
    assert "rag text" not in prompt_text
    assert "rag image" not in prompt_text


def test_clear_resets_rag_prefix_len(shell):
    rag_msg = UserMessage(text="rag context")
    shell.conversation_history = [rag_msg] + make_history(("a", "b"))
    shell.rag_prefix_len = 1
    shell.default("/clear")
    assert shell.rag_prefix_len == 0
    assert shell.conversation_history == []
    # One call to _check_and_summarize increments message_count by 2, below the
    # summarize_after=4 threshold, so _summarize_conversation is never reached.
    shell._check_and_summarize()
    assert shell.message_count == 2


def test_summarize_after_clear_does_not_treat_new_exchange_as_rag(shell, monkeypatch):
    """After /clear, new exchanges must be summarizable, not frozen as RAG prefix."""
    rag_msg = UserMessage(text="rag context")
    shell.conversation_history = [rag_msg] + make_history(("a", "b"))
    shell.rag_prefix_len = 1
    shell.default("/clear")

    # Add two exchanges and drive both through _check_and_summarize to hit the
    # summarize_after=4 threshold without calling _summarize_conversation directly.
    shell.conversation_history = make_history(("c", "d"), ("e", "f"))
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: mock_summary_response("new summary"))
    shell._check_and_summarize()
    shell._check_and_summarize()

    summary_msgs = [m for m in shell.conversation_history if isinstance(m, SystemMessage)]
    assert len(summary_msgs) == 1
    assert "new summary" in summary_msgs[0].text


def test_summarize_api_failure_preserves_history(shell, monkeypatch):
    shell.conversation_history = make_history(("a", "b"), ("c", "d"), ("e", "f"))
    original = list(shell.conversation_history)

    def raise_url_error(*a, **kw):
        raise urllib.error.URLError("network error")

    monkeypatch.setattr(urllib.request, "urlopen", raise_url_error)
    shell._summarize_conversation()
    assert shell.conversation_history == original
