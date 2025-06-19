import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# Import the chat module to test integration
from ramalama.chat import chat
from ramalama.file_upload.file_loader import FileUpLoader


class TestFileUploadChatIntegration:
    """Test integration between file upload functionality and chat functionality."""

    def test_chat_with_file_input_single_file(self):
        """Test chat functionality with a single file input."""
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_file:
            with open(tmp_file.name, "w") as f:
                f.write("This is test content for chat input")

            mock_args = MagicMock()
            mock_args.input = tmp_file.name
            mock_args.ARGS = "Please analyze this content:"
            mock_args.dryrun = True

            with patch('ramalama.chat.dry_run') as mock_dry_run:
                with patch('builtins.print') as mock_print:
                    chat(mock_args)

                    call_args = mock_dry_run.call_args[0][0]

                    assert "Please analyze this content:" in call_args
                    assert "This is test content for chat input" in call_args
                    assert f"<!--start_document {tmp_file.name}-->" in call_args

                    mock_print.assert_called()

    def test_chat_with_file_input_directory(self):
        """Test chat functionality with a directory input."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            txt_file = os.path.join(tmp_dir, "test.txt")
            with open(txt_file, "w") as f:
                f.write("Text file content")

            md_file = os.path.join(tmp_dir, "readme.md")
            with open(md_file, "w") as f:
                f.write("# Markdown Content\n\nThis is a test.")

            mock_args = MagicMock()
            mock_args.input = tmp_dir
            mock_args.ARGS = "Please analyze these files:"
            mock_args.dryrun = True

            with patch('ramalama.chat.dry_run') as mock_dry_run:
                mock_dry_run.return_value = "mocked_dry_run_output"

                with patch('builtins.print') as mock_print:
                    chat(mock_args)

                    call_args = mock_dry_run.call_args[0][0]

                    assert "Please analyze these files:" in call_args
                    assert "Text file content" in call_args
                    assert "# Markdown Content" in call_args
                    assert "test.txt" in call_args
                    assert "readme.md" in call_args
                    assert "<!--start_document" in call_args

    def test_chat_with_file_input_no_files(self):
        """Test chat functionality with input directory containing no supported files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            unsupported_file = os.path.join(tmp_dir, "test.xyz")
            with open(unsupported_file, "w") as f:
                f.write("Unsupported content")

            mock_args = MagicMock()
            mock_args.input = tmp_dir
            mock_args.ARGS = "Please analyze:"
            mock_args.dryrun = True

            with patch('ramalama.chat.dry_run') as mock_dry_run:
                mock_dry_run.return_value = "mocked_dry_run_output"

                with patch('builtins.print') as mock_print:
                    chat(mock_args)

                    mock_dry_run.assert_called_once()
                    call_args = mock_dry_run.call_args[0][0]

                    assert call_args == "Please analyze:"

    def test_chat_with_file_input_nonexistent_file(self):
        """Test chat functionality with non-existent file input."""
        mock_args = MagicMock()
        mock_args.input = "/nonexistent/file.txt"
        mock_args.ARGS = "Please analyze:"
        mock_args.dryrun = True

        with pytest.raises(ValueError, match="does not exist"):
            chat(mock_args)

    def test_chat_with_file_input_empty_file(self):
        """Test chat functionality with an empty file."""
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_file:
            with open(tmp_file.name, "w") as f:
                f.write("")

            mock_args = MagicMock()
            mock_args.input = tmp_file.name
            mock_args.ARGS = "Please analyze:"
            mock_args.dryrun = True

            with patch('ramalama.chat.dry_run') as mock_dry_run:
                mock_dry_run.return_value = "mocked_dry_run_output"

                with patch('builtins.print') as mock_print:
                    chat(mock_args)

                    call_args = mock_dry_run.call_args[0][0]

                    assert "Please analyze:" in call_args
                    assert f"<!--start_document {tmp_file.name}-->" in call_args
                    assert call_args.endswith(f"\n<!--start_document {tmp_file.name}-->\n")

    def test_chat_with_file_input_unicode_content(self):
        """Test chat functionality with Unicode content in files."""
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_file:
            unicode_content = "Hello 世界! 🌍\nUnicode test: éñü\nEmoji: 🚀🎉"
            with open(tmp_file.name, "w") as f:
                f.write(unicode_content)

            mock_args = MagicMock()
            mock_args.input = tmp_file.name
            mock_args.ARGS = "Please analyze:"
            mock_args.dryrun = True

            with patch('ramalama.chat.dry_run') as mock_dry_run:
                mock_dry_run.return_value = "mocked_dry_run_output"

                with patch('builtins.print') as mock_print:
                    chat(mock_args)

                    mock_dry_run.assert_called_once()
                    call_args = mock_dry_run.call_args[0][0]

                    assert "Please analyze:" in call_args
                    assert unicode_content in call_args
                    assert f"<!--start_document {tmp_file.name}-->" in call_args

    def test_chat_with_file_input_mixed_content_types(self):
        """Test chat functionality with mixed content types."""
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
            mock_args.input = tmp_dir
            mock_args.ARGS = "Please analyze these files:"
            mock_args.dryrun = True

            with patch('ramalama.chat.dry_run') as mock_dry_run:
                mock_dry_run.return_value = "mocked_dry_run_output"

                with patch('builtins.print') as mock_print:
                    chat(mock_args)

                    mock_dry_run.assert_called_once()
                    call_args = mock_dry_run.call_args[0][0]

                    assert "Please analyze these files:" in call_args
                    assert "English content" in call_args
                    assert '{"key": "value", "number": 42}' in call_args
                    assert "setting: enabled" in call_args
                    assert "values:" in call_args
                    assert "english.txt" in call_args
                    assert "data.json" in call_args
                    assert "config.yaml" in call_args

    def test_chat_with_file_input_no_input_specified(self):
        """Test chat functionality when no input file is specified."""
        mock_args = MagicMock()
        mock_args.input = None
        mock_args.ARGS = "Please analyze:"
        mock_args.dryrun = True

        with patch('ramalama.chat.dry_run') as mock_dry_run:
            mock_dry_run.return_value = "mocked_dry_run_output"

            with patch('builtins.print') as mock_print:
                chat(mock_args)

                mock_dry_run.assert_called_once()
                call_args = mock_dry_run.call_args[0][0]

                assert call_args == "Please analyze:"

    def test_chat_with_file_input_empty_args(self):
        """Test chat functionality with empty ARGS but file input."""
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_file:
            with open(tmp_file.name, "w") as f:
                f.write("File content")

            mock_args = MagicMock()
            mock_args.input = tmp_file.name
            mock_args.ARGS = None
            mock_args.dryrun = True

            with patch('ramalama.chat.dry_run') as mock_dry_run:
                mock_dry_run.return_value = "mocked_dry_run_output"

                with patch('builtins.print') as mock_print:
                    chat(mock_args)

                    mock_dry_run.assert_called_once()
                    call_args = mock_dry_run.call_args[0][0]

                    assert "File content" in call_args
                    assert f"<!--start_document {tmp_file.name}-->" in call_args

                    assert not call_args.startswith("None")
