from unittest.mock import MagicMock

from ramalama.chat import RamaLamaShell


def test_input_with_backslash():
    # fake arguments to not get errors
    mock_args = MagicMock()
    mock_args.prefix = "> "
    mock_args.url = "http://localhost:8080"
    mock_args.model = "test-model"
    mock_args.rag = None
    mock_args.mcp = []
    mock_args.summarize_after = 0
    mock_args.color = "never"

    # instance of RamaLamaShell with the fake args
    ramalama = RamaLamaShell(mock_args)

    # disable network function
    ramalama._req = MagicMock(return_value="Answer")

    # Case 1, with backslash
    assert ramalama.default("Hola\\") is False
    assert ramalama.content == ["Hola"]

    # Verify that _req was not called
    ramalama._req.assert_not_called()


def test_input_continuation_with_backslash():
    # fake arguments to not get errors
    mock_args = MagicMock()
    mock_args.prefix = "> "
    mock_args.url = "http://localhost:8080"
    mock_args.model = "test-model"
    mock_args.rag = None
    mock_args.mcp = []
    mock_args.summarize_after = 0
    mock_args.color = "never"

    # instance of RamaLamaShell with the fake args
    ramalama = RamaLamaShell(mock_args)
    ramalama._req = MagicMock(return_value="Answer")  # disable network function

    # case 2, we add text after backslash
    assert ramalama.default("Hola \\") is False
    assert ramalama.content == ["Hola "]

    # Verify that _req was not called
    ramalama._req.assert_not_called()

    # we add text after
    assert ramalama.default("Mundo") is not False
    assert ramalama.content == []

    # Verify that _req was called
    ramalama._req.assert_called_once()


def test_input_without_backslash():
    # fake arguments to not get errors
    mock_args = MagicMock()
    mock_args.prefix = "> "
    mock_args.url = "http://localhost:8080"
    mock_args.model = "test-model"
    mock_args.rag = None
    mock_args.mcp = []
    mock_args.summarize_after = 0
    mock_args.color = "never"

    # instance of RamaLamaShell with the fake args
    ramalama = RamaLamaShell(mock_args)
    ramalama._req = MagicMock(return_value="Answer")  # disable network function

    # case 3, no backslash
    result = ramalama.default("Hola")
    assert result is not False  # it does not return True
    assert ramalama.content == []  # the message has been sended

    # Verify that _req was called
    ramalama._req.assert_called_once()
