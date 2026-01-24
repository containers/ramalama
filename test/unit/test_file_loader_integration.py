import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from ramalama.chat import RamaLamaShell, chat
from ramalama.chat_utils import ImageURLPart


def _text_content(message):
    return message.text or ""


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
            message = shell.conversation_history[0]
            assert message.role == "user"
            content = message.text or ""
            assert "This is test content for chat input" in content
            assert f"<!--start_document {tmp_file.name}-->" in content

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
            message = shell.conversation_history[0]
            assert message.role == "user"
            content = message.text or ""
            assert "Text file content" in content
            assert "# Markdown Content" in content
            assert "test.txt" in content
            assert "readme.md" in content
            assert "<!--start_document" in content

    @pytest.mark.filterwarnings("ignore:.*Unsupported file types detected!.*")
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
            message = shell.conversation_history[0]
            assert message.role == "user"
            text = _text_content(message)
            assert f"<!--start_document {tmp_file.name}-->" in text
            assert text.endswith(f"\n<!--start_document {tmp_file.name}-->\n")

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
            message = shell.conversation_history[0]
            assert message.role == "user"
            text = message.text or ""
            assert unicode_content in text
            assert f"<!--start_document {tmp_file.name}-->" in text

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
            message = shell.conversation_history[0]
            assert message.role == "user"
            text = _text_content(message)
            assert "English content" in text
            assert '{"key": "value", "number": 42}' in text
            assert "setting: enabled" in text
            assert "values:" in text
            assert "english.txt" in text
            assert "data.json" in text
            assert "config.yaml" in text

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
            message = shell.conversation_history[0]
            assert message.role == "user"
            text = _text_content(message)
            assert "File content" in text
            assert f"<!--start_document {tmp_file.name}-->" in text

    def test_chat_function_with_rag_and_dryrun(self):
        """Test that chat function works correctly with rag and dryrun."""
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_file:
            with open(tmp_file.name, "w") as f:
                f.write("Test content")

            mock_args = MagicMock()
            mock_args.rag = tmp_file.name
            mock_args.ARGS = ["Please analyze:"]
            mock_args.dryrun = True

            with patch('builtins.print') as mock_print:
                chat(mock_args)

                # print should only be called with ARGS, not the file content
                mock_print.assert_called_once()
                assert len(mock_print.call_args.args) == 1
                call_args = mock_print.call_args.args[0]
                assert call_args.endswith("Please analyze:")
                # File content should not be in the dry_run call
                assert "Test content" not in call_args
                assert f"<!--start_document {tmp_file.name}-->" not in call_args


class TestImageUploadChatIntegration:
    """Test integration between image upload functionality and chat functionality."""

    @patch('urllib.request.urlopen')
    def test_chat_with_image_input_single_file(self, mock_urlopen):
        """Test chat functionality with a single image file input."""
        # Mock the models endpoint response
        mock_response = MagicMock()
        mock_response.__iter__.return_value = [b'{"data": [{"id": "test-model"}]}']
        mock_urlopen.return_value = mock_response

        with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp_file:
            with open(tmp_file.name, "wb") as f:
                f.write(b"fake image data")

            mock_args = MagicMock()
            mock_args.rag = tmp_file.name
            mock_args.ARGS = ["Please analyze this image:"]
            mock_args.dryrun = False

            shell = RamaLamaShell(mock_args)

            # Check that the system message was added to conversation history
            assert len(shell.conversation_history) == 1
            message = shell.conversation_history[0]
            assert message.role == "user"
            assert len(message.attachments) == 1
            part = message.attachments[0]
            assert isinstance(part, ImageURLPart)
            assert part.url.startswith("data:image/")
            assert "base64," in part.url

    @patch('urllib.request.urlopen')
    def test_chat_with_image_input_directory(self, mock_urlopen):
        """Test chat functionality with a directory containing images."""
        # Mock the models endpoint response
        mock_response = MagicMock()
        mock_response.__iter__.return_value = [b'{"data": [{"id": "test-model"}]}']
        mock_urlopen.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmp_dir:
            jpg_file = os.path.join(tmp_dir, "test.jpg")
            with open(jpg_file, "wb") as f:
                f.write(b"jpg image data")

            png_file = os.path.join(tmp_dir, "test.png")
            with open(png_file, "wb") as f:
                f.write(b"png image data")

            mock_args = MagicMock()
            mock_args.rag = tmp_dir
            mock_args.ARGS = ["Please analyze these images:"]
            mock_args.dryrun = False

            shell = RamaLamaShell(mock_args)

            # Check that the system message was added to conversation history
            assert len(shell.conversation_history) == 1
            message = shell.conversation_history[0]
            assert message.role == "user"
            assert len(message.attachments) == 2
            for part in message.attachments:
                assert isinstance(part, ImageURLPart)
                assert "data:image/" in part.url
                assert "base64," in part.url

    @patch('urllib.request.urlopen')
    def test_chat_with_image_input_mixed_file_types(self, mock_urlopen):
        """Test chat functionality with mixed text and image files."""
        # Mock the models endpoint response
        mock_response = MagicMock()
        mock_response.__iter__.return_value = [b'{"data": [{"id": "test-model"}]}']
        mock_urlopen.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmp_dir:
            txt_file = os.path.join(tmp_dir, "readme.txt")
            with open(txt_file, "w") as f:
                f.write("Text content")

            jpg_file = os.path.join(tmp_dir, "image.jpg")
            with open(jpg_file, "wb") as f:
                f.write(b"image data")

            mock_args = MagicMock()
            mock_args.rag = tmp_dir
            mock_args.ARGS = ["Please analyze these files:"]
            mock_args.dryrun = False

            shell = RamaLamaShell(mock_args)

            # Check that two system messages were added to conversation history
            user_messages = [msg for msg in shell.conversation_history if msg.role == "user"]
            assert len(user_messages) == 2

            # Determine which message is text and which is image
            if user_messages[0].attachments:
                image_msg = user_messages[0]
                text_msg = user_messages[1]
            else:
                text_msg = user_messages[0]
                image_msg = user_messages[1]

            text = _text_content(text_msg)
            assert "Text content" in text
            assert "readme.txt" in text

            assert any(isinstance(part, ImageURLPart) for part in image_msg.attachments)

    @pytest.mark.filterwarnings("ignore:.*Unsupported file types detected!.*")
    @patch('urllib.request.urlopen')
    def test_chat_with_image_input_unsupported_image_types(self, mock_urlopen):
        """Test chat functionality with unsupported image file types."""
        # Mock the models endpoint response
        mock_response = MagicMock()
        mock_response.__iter__.return_value = [b'{"data": [{"id": "test-model"}]}']
        mock_urlopen.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmp_dir:
            unsupported_file = os.path.join(tmp_dir, "test.xyz")
            with open(unsupported_file, "wb") as f:
                f.write(b"Unsupported image data")

            mock_args = MagicMock()
            mock_args.rag = tmp_dir
            mock_args.ARGS = ["Please analyze:"]
            mock_args.dryrun = False

            shell = RamaLamaShell(mock_args)

            # Check that no system message was added since no supported files
            assert len(shell.conversation_history) == 0

    @patch('urllib.request.urlopen')
    def test_chat_with_image_input_case_insensitive_extensions(self, mock_urlopen):
        """Test chat functionality with case-insensitive image extensions."""
        # Mock the models endpoint response
        mock_response = MagicMock()
        mock_response.__iter__.return_value = [b'{"data": [{"id": "test-model"}]}']
        mock_urlopen.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmp_dir:
            jpg_file = os.path.join(tmp_dir, "test.JPG")
            with open(jpg_file, "wb") as f:
                f.write(b"Uppercase JPG data")

            png_file = os.path.join(tmp_dir, "test.PNG")
            with open(png_file, "wb") as f:
                f.write(b"Uppercase PNG data")

            mock_args = MagicMock()
            mock_args.rag = tmp_dir
            mock_args.ARGS = ["Please analyze these images:"]
            mock_args.dryrun = False

            shell = RamaLamaShell(mock_args)

            # Check that the system message was added to conversation history
            assert len(shell.conversation_history) == 1
            message = shell.conversation_history[0]
            assert message.role == "user"
            assert len(message.attachments) == 2
            for part in message.attachments:
                assert isinstance(part, ImageURLPart)
                assert "data:image/" in part.url
                assert "base64," in part.url
