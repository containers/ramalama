import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from ramalama.chat import RamaLamaShell, chat


class TestFileUploadChatIntegration:
    """Test integration between file upload functionality and chat functionality."""

    @patch('urllib.request.urlopen')
    def test_chat_with_file_input_single_file(self, mock_urlopen):
        """Test chat functionality with a single file input."""
        # Mock the models endpoint response
        mock_response = MagicMock()
        mock_response.__iter__.return_value = [b'{"data": [{"id": "test-model"}]}']
        mock_urlopen.return_value = mock_response

        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_file:
            with open(tmp_file.name, "w") as f:
                f.write("This is test content for chat input")

            mock_args = MagicMock()
            mock_args.rag = tmp_file.name
            mock_args.ARGS = ["Please analyze this content:"]
            mock_args.dryrun = False

            shell = RamaLamaShell(mock_args)

            # Check that the system message was added to conversation history
            assert len(shell.conversation_history) == 1
            system_message = shell.conversation_history[0]
            assert system_message["role"] == "system"
            assert "This is test content for chat input" in system_message["content"]
            assert f"<!--start_document {tmp_file.name}-->" in system_message["content"]

    @patch('urllib.request.urlopen')
    def test_chat_with_file_input_directory(self, mock_urlopen):
        """Test chat functionality with a directory input."""
        # Mock the models endpoint response
        mock_response = MagicMock()
        mock_response.__iter__.return_value = [b'{"data": [{"id": "test-model"}]}']
        mock_urlopen.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmp_dir:
            txt_file = os.path.join(tmp_dir, "test.txt")
            with open(txt_file, "w") as f:
                f.write("Text file content")

            md_file = os.path.join(tmp_dir, "readme.md")
            with open(md_file, "w") as f:
                f.write("# Markdown Content\n\nThis is a test.")

            mock_args = MagicMock()
            mock_args.rag = tmp_dir
            mock_args.ARGS = ["Please analyze these files:"]
            mock_args.dryrun = False

            shell = RamaLamaShell(mock_args)

            # Check that the system message was added to conversation history
            assert len(shell.conversation_history) == 1
            system_message = shell.conversation_history[0]
            assert system_message["role"] == "system"
            assert "Text file content" in system_message["content"]
            assert "# Markdown Content" in system_message["content"]
            assert "test.txt" in system_message["content"]
            assert "readme.md" in system_message["content"]
            assert "<!--start_document" in system_message["content"]

    @patch('urllib.request.urlopen')
    def test_chat_with_file_input_no_files(self, mock_urlopen):
        """Test chat functionality with input directory containing no supported files."""
        # Mock the models endpoint response
        mock_response = MagicMock()
        mock_response.__iter__.return_value = [b'{"data": [{"id": "test-model"}]}']
        mock_urlopen.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmp_dir:
            unsupported_file = os.path.join(tmp_dir, "test.xyz")
            with open(unsupported_file, "w") as f:
                f.write("Unsupported content")

            mock_args = MagicMock()
            mock_args.rag = tmp_dir
            mock_args.ARGS = ["Please analyze:"]
            mock_args.dryrun = False

            shell = RamaLamaShell(mock_args)

            # Check that no system message was added since no supported files
            assert len(shell.conversation_history) == 0

    def test_chat_with_file_input_nonexistent_file(self):
        """Test chat functionality with non-existent file input."""
        mock_args = MagicMock()
        mock_args.rag = "/nonexistent/file.txt"
        mock_args.ARGS = ["Please analyze:"]
        mock_args.dryrun = False

        with pytest.raises(ValueError, match="does not exist"):
            RamaLamaShell(mock_args)

    @patch('urllib.request.urlopen')
    def test_chat_with_file_input_empty_file(self, mock_urlopen):
        """Test chat functionality with an empty file."""
        # Mock the models endpoint response
        mock_response = MagicMock()
        mock_response.__iter__.return_value = [b'{"data": [{"id": "test-model"}]}']
        mock_urlopen.return_value = mock_response

        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_file:
            with open(tmp_file.name, "w") as f:
                f.write("")

            mock_args = MagicMock()
            mock_args.rag = tmp_file.name
            mock_args.ARGS = ["Please analyze:"]
            mock_args.dryrun = False

            shell = RamaLamaShell(mock_args)

            # Check that the system message was added to conversation history
            assert len(shell.conversation_history) == 1
            system_message = shell.conversation_history[0]
            assert system_message["role"] == "system"
            assert f"<!--start_document {tmp_file.name}-->" in system_message["content"]
            # Empty file should still have the delimiter but no content
            assert system_message["content"].endswith(f"\n<!--start_document {tmp_file.name}-->\n")

    @patch('urllib.request.urlopen')
    def test_chat_with_file_input_unicode_content(self, mock_urlopen):
        """Test chat functionality with Unicode content in files."""
        # Mock the models endpoint response
        mock_response = MagicMock()
        mock_response.__iter__.return_value = [b'{"data": [{"id": "test-model"}]}']
        mock_urlopen.return_value = mock_response

        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_file:
            unicode_content = "Hello 世界! 🌍\nUnicode test: éñü\nEmoji: 🚀🎉"
            with open(tmp_file.name, "w") as f:
                f.write(unicode_content)

            mock_args = MagicMock()
            mock_args.rag = tmp_file.name
            mock_args.ARGS = ["Please analyze:"]
            mock_args.dryrun = False

            shell = RamaLamaShell(mock_args)

            # Check that the system message was added to conversation history
            assert len(shell.conversation_history) == 1
            system_message = shell.conversation_history[0]
            assert system_message["role"] == "system"
            assert unicode_content in system_message["content"]
            assert f"<!--start_document {tmp_file.name}-->" in system_message["content"]

    @patch('urllib.request.urlopen')
    def test_chat_with_file_input_mixed_content_types(self, mock_urlopen):
        """Test chat functionality with mixed content types."""
        # Mock the models endpoint response
        mock_response = MagicMock()
        mock_response.__iter__.return_value = [b'{"data": [{"id": "test-model"}]}']
        mock_urlopen.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmp_dir:
            txt_file = os.path.join(tmp_dir, "english.txt")
            with open(txt_file, "w") as f:
                f.write("English content")

            json_file = os.path.join(tmp_dir, "data.json")
            with open(json_file, "w") as f:
                f.write('{"key": "value", "number": 42}')

            yaml_file = os.path.join(tmp_dir, "config.yaml")
            with open(yaml_file, "w") as f:
                f.write("setting: enabled\nvalues:\n  - one\n  - two")

            mock_args = MagicMock()
            mock_args.rag = tmp_dir
            mock_args.ARGS = ["Please analyze these files:"]
            mock_args.dryrun = False

            shell = RamaLamaShell(mock_args)

            # Check that the system message was added to conversation history
            assert len(shell.conversation_history) == 1
            system_message = shell.conversation_history[0]
            assert system_message["role"] == "system"
            assert "English content" in system_message["content"]
            assert '{"key": "value", "number": 42}' in system_message["content"]
            assert "setting: enabled" in system_message["content"]
            assert "values:" in system_message["content"]
            assert "english.txt" in system_message["content"]
            assert "data.json" in system_message["content"]
            assert "config.yaml" in system_message["content"]

    @patch('urllib.request.urlopen')
    def test_chat_with_file_input_no_input_specified(self, mock_urlopen):
        """Test chat functionality when no input file is specified."""
        # Mock the models endpoint response
        mock_response = MagicMock()
        mock_response.__iter__.return_value = [b'{"data": [{"id": "test-model"}]}']
        mock_urlopen.return_value = mock_response

        mock_args = MagicMock()
        mock_args.rag = None
        mock_args.ARGS = ["Please analyze:"]
        mock_args.dryrun = False

        shell = RamaLamaShell(mock_args)

        # Check that no system message was added since no rag specified
        assert len(shell.conversation_history) == 0

    @patch('urllib.request.urlopen')
    def test_chat_with_file_input_empty_args(self, mock_urlopen):
        """Test chat functionality with empty ARGS but file input."""
        # Mock the models endpoint response
        mock_response = MagicMock()
        mock_response.__iter__.return_value = [b'{"data": [{"id": "test-model"}]}']
        mock_urlopen.return_value = mock_response

        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_file:
            with open(tmp_file.name, "w") as f:
                f.write("File content")

            mock_args = MagicMock()
            mock_args.rag = tmp_file.name
            mock_args.ARGS = None
            mock_args.dryrun = False

            shell = RamaLamaShell(mock_args)

            # Check that the system message was added to conversation history
            assert len(shell.conversation_history) == 1
            system_message = shell.conversation_history[0]
            assert system_message["role"] == "system"
            assert "File content" in system_message["content"]
            assert f"<!--start_document {tmp_file.name}-->" in system_message["content"]

    def test_chat_function_with_rag_and_dryrun(self):
        """Test that chat function works correctly with rag and dryrun."""
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_file:
            with open(tmp_file.name, "w") as f:
                f.write("Test content")

            mock_args = MagicMock()
            mock_args.rag = tmp_file.name
            mock_args.ARGS = ["Please analyze:"]
            mock_args.dryrun = True

            with patch('ramalama.chat.dry_run') as mock_dry_run:
                with patch('builtins.print') as mock_print:
                    chat(mock_args)

                    # dry_run should only be called with ARGS, not the file content
                    mock_dry_run.assert_called_once()
                    call_args = ' '.join(mock_dry_run.call_args[0][0])
                    assert call_args == "Please analyze:"
                    # File content should not be in the dry_run call
                    assert "Test content" not in call_args
                    assert f"<!--start_document {tmp_file.name}-->" not in call_args

                    mock_print.assert_called()
