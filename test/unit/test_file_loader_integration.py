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
            system_message = shell.conversation_history[0]
            assert system_message["role"] == "system"
            assert isinstance(system_message["content"], list)
            assert len(system_message["content"]) == 1
            assert 'image_url' in system_message["content"][0]
            assert 'url' in system_message["content"][0]["image_url"]
            assert "data:image/" in system_message["content"][0]["image_url"]["url"]
            assert "base64," in system_message["content"][0]["image_url"]["url"]

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
            system_message = shell.conversation_history[0]
            assert system_message["role"] == "system"
            assert isinstance(system_message["content"], list)
            assert len(system_message["content"]) == 2
            assert all('image_url' in item for item in system_message["content"])
            assert all('url' in item["image_url"] for item in system_message["content"])
            assert all("data:image/" in item["image_url"]["url"] for item in system_message["content"])
            assert all("base64," in item["image_url"]["url"] for item in system_message["content"])

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
            system_messages = [msg for msg in shell.conversation_history if msg["role"] == "system"]
            assert len(system_messages) == 2

            # Determine which message is text and which is image
            if isinstance(system_messages[0]["content"], str):
                text_msg = system_messages[0]
                image_msg = system_messages[1]
            else:
                text_msg = system_messages[1]
                image_msg = system_messages[0]

            # Assert text message content
            assert "Text content" in text_msg["content"]
            assert "readme.txt" in text_msg["content"]

            # Assert image message content
            assert isinstance(image_msg["content"], list)
            assert any(
                isinstance(item, dict)
                and "image_url" in item
                and "url" in item["image_url"]
                and "data:image/" in item["image_url"]["url"]
                for item in image_msg["content"]
            )

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
            system_message = shell.conversation_history[0]
            assert system_message["role"] == "system"
            assert isinstance(system_message["content"], list)
            assert len(system_message["content"]) == 2
            assert all('image_url' in item for item in system_message["content"])
            assert all('url' in item["image_url"] for item in system_message["content"])
            assert all("data:image/" in item["image_url"]["url"] for item in system_message["content"])
            assert all("base64," in item["image_url"]["url"] for item in system_message["content"])
