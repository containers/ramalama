import os
import tempfile
from unittest.mock import MagicMock, mock_open, patch

import pytest

from ramalama.file_upload.file_loader import SUPPORTED_EXTENSIONS, BaseFileUploader, FileUpLoader
from ramalama.file_upload.file_types.base import BaseFileUpload
from ramalama.file_upload.file_types.txt import TXTFileUpload


class TestBaseFileUpload:
    """Test the abstract base class for file upload handlers."""

    def test_base_file_upload_is_abstract(self):
        """Test that BaseFileUpload cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseFileUpload("/path/to/file.txt")


class TestTXTFileUpload:
    """Test the text file upload handler."""

    def test_txt_file_upload_initialization(self):
        """Test that TXTFileUpload can be initialized."""
        file_path = "/path/to/test.txt"
        uploader = TXTFileUpload(file_path)
        assert uploader.file == file_path
        assert isinstance(uploader, BaseFileUpload)

    def test_txt_file_upload_load_content(self):
        """Test loading content from a text file."""
        test_content = "This is test content\nwith multiple lines."

        with patch("builtins.open", mock_open(read_data=test_content)):
            uploader = TXTFileUpload("/path/to/test.txt")
            result = uploader.load()

        assert result == test_content

    def test_txt_file_upload_load_empty_file(self):
        """Test loading content from an empty text file."""
        with patch("builtins.open", mock_open(read_data="")):
            uploader = TXTFileUpload("/path/to/empty.txt")
            result = uploader.load()

        assert result == ""

    def test_txt_file_upload_load_unicode_content(self):
        """Test loading Unicode content from a text file."""
        test_content = "Hello 世界! 🌍\nUnicode test: éñü"

        with patch("builtins.open", mock_open(read_data=test_content)):
            uploader = TXTFileUpload("/path/to/unicode.txt")
            result = uploader.load()

        assert result == test_content


class TestBaseFileUploader:
    """Test the base file uploader class."""

    def test_base_file_uploader_initialization(self):
        """Test that BaseFileUploader can be initialized with files and delimiter."""
        mock_files = [MagicMock(), MagicMock()]
        uploader = BaseFileUploader(files=mock_files)

        assert uploader.files == mock_files
        assert uploader.document_delimiter is not None

    def test_base_file_uploader_initialization_custom_delimiter(self):
        """Test that BaseFileUploader can be initialized with custom delimiter."""
        mock_files = [MagicMock()]
        custom_delimiter = "---START $name---"
        uploader = BaseFileUploader(files=mock_files, delim_string=custom_delimiter)

        assert uploader.files == mock_files
        assert uploader.document_delimiter.template == custom_delimiter

    def test_base_file_uploader_load_single_file(self):
        """Test loading a single file."""
        mock_file = MagicMock()
        mock_file.file = "test.txt"
        mock_file.load.return_value = "Test content"

        uploader = BaseFileUploader(files=[mock_file])
        result = uploader.load()

        expected = "\n<!--start_document test.txt-->\nTest content"
        assert result == expected

    def test_base_file_uploader_load_multiple_files(self):
        """Test loading multiple files."""
        mock_file1 = MagicMock()
        mock_file1.file = "test1.txt"
        mock_file1.load.return_value = "Content 1"

        mock_file2 = MagicMock()
        mock_file2.file = "test2.txt"
        mock_file2.load.return_value = "Content 2"

        uploader = BaseFileUploader(files=[mock_file1, mock_file2])
        result = uploader.load()

        expected = "\n<!--start_document test1.txt-->\nContent 1\n<!--start_document test2.txt-->\nContent 2"
        assert result == expected

    def test_base_file_uploader_load_empty_file_list(self):
        """Test loading with empty file list."""
        uploader = BaseFileUploader(files=[])
        result = uploader.load()

        assert result == ""


class TestFileUpLoader:
    """Test the main file uploader class."""

    def test_file_uploader_initialization_single_file(self):
        """Test initializing FileUpLoader with a single file."""
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_file:
            with open(tmp_file.name, "w") as f:
                f.write("Test content")

            uploader = FileUpLoader(tmp_file.name)
            assert len(uploader.files) == 1
            assert isinstance(uploader.files[0], TXTFileUpload)
            assert uploader.files[0].file == tmp_file.name

    def test_file_uploader_initialization_directory(self):
        """Test initializing FileUpLoader with a directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            txt_file = os.path.join(tmp_dir, "test.txt")
            with open(txt_file, "w") as f:
                f.write("Text content")

            md_file = os.path.join(tmp_dir, "test.md")
            with open(md_file, "w") as f:
                f.write("# Markdown content")

            uploader = FileUpLoader(tmp_dir)
            assert len(uploader.files) == 2
            assert {txt_file, md_file} == {f.file for f in uploader.files}

    def test_file_uploader_initialization_nonexistent_file(self):
        """Test initializing FileUpLoader with a non-existent file."""
        with pytest.raises(ValueError, match="does not exist"):
            FileUpLoader("/nonexistent/file.txt")

    def test_file_uploader_initialization_nonexistent_directory(self):
        """Test initializing FileUpLoader with a non-existent directory."""
        with pytest.raises(ValueError, match="does not exist"):
            FileUpLoader("/nonexistent/directory")

    def test_file_uploader_load_single_text_file(self):
        """Test loading a single text file."""
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_file:
            with open(tmp_file.name, "w") as f:
                f.write("Test content\nwith multiple lines")

            uploader = FileUpLoader(tmp_file.name)
            result = uploader.load()

            expected = f"\n<!--start_document {tmp_file.name}-->\nTest content\nwith multiple lines"
            assert result == expected

    def test_file_uploader_load_multiple_files(self):
        """Test loading multiple files from a directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            txt_file = os.path.join(tmp_dir, "test.txt")
            with open(txt_file, "w") as f:
                f.write("Text content")

            md_file = os.path.join(tmp_dir, "test.md")
            with open(md_file, "w") as f:
                f.write("# Markdown content")

            uploader = FileUpLoader(tmp_dir)
            result = uploader.load()

            assert "<!--start_document" in result
            assert "Text content" in result
            assert "# Markdown content" in result
            assert "test.txt" in result
            assert "test.md" in result

    def test_file_uploader_unsupported_file_types(self):
        """Test handling of unsupported file types."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            unsupported_file = os.path.join(tmp_dir, "test.xyz")
            with open(unsupported_file, "w") as f:
                f.write("Unsupported content")

            uploader = FileUpLoader(tmp_dir)
            assert len(uploader.files) == 0

    def test_file_uploader_mixed_supported_unsupported_files(self):
        """Test handling of mixed supported and unsupported file types."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            txt_file = os.path.join(tmp_dir, "test.txt")
            with open(txt_file, "w") as f:
                f.write("Supported content")

            unsupported_file = os.path.join(tmp_dir, "test.xyz")
            with open(unsupported_file, "w") as f:
                f.write("Unsupported content")

            uploader = FileUpLoader(tmp_dir)

            assert len(uploader.files) == 1
            assert uploader.files[0].file == txt_file

    def test_file_uploader_empty_directory(self):
        """Test handling of empty directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            uploader = FileUpLoader(tmp_dir)
            assert len(uploader.files) == 0
            result = uploader.load()
            assert result == ""

    def test_file_uploader_case_insensitive_extensions(self):
        """Test that file extensions are handled case-insensitively."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            txt_file = os.path.join(tmp_dir, "test.TXT")
            with open(txt_file, "w") as f:
                f.write("Uppercase extension")

            md_file = os.path.join(tmp_dir, "test.MD")
            with open(md_file, "w") as f:
                f.write("Uppercase markdown")

            uploader = FileUpLoader(tmp_dir)

            assert len(uploader.files) == 2


class TestSupportedExtensions:
    """Test the supported extensions mapping."""

    def test_supported_extensions_mapping(self):
        """Test that all supported extensions map to correct classes."""
        assert SUPPORTED_EXTENSIONS['.txt'] == TXTFileUpload
        assert SUPPORTED_EXTENSIONS['.sh'] == TXTFileUpload
        assert SUPPORTED_EXTENSIONS['.md'] == TXTFileUpload
        assert SUPPORTED_EXTENSIONS['.yaml'] == TXTFileUpload
        assert SUPPORTED_EXTENSIONS['.yml'] == TXTFileUpload
        assert SUPPORTED_EXTENSIONS['.json'] == TXTFileUpload
        assert SUPPORTED_EXTENSIONS['.csv'] == TXTFileUpload
        assert SUPPORTED_EXTENSIONS['.toml'] == TXTFileUpload


class TestFileUploadIntegration:
    """Test integration scenarios for file upload functionality."""

    def test_file_upload_with_various_text_formats(self):
        """Test uploading various text-based file formats."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            files_content = {
                "test.txt": "Plain text content",
                "script.sh": "#!/bin/bash\necho 'Hello World'",
                "readme.md": "# Test Markdown\n\nThis is a test.",
                "config.yaml": "key: value\nlist:\n  - item1\n  - item2",
                "data.json": '{"name": "test", "value": 42}',
                "data.csv": "name,value\ntest,42",
                "config.toml": "[section]\nkey = 'value'",
            }

            for filename, content in files_content.items():
                file_path = os.path.join(tmp_dir, filename)
                with open(file_path, "w") as f:
                    f.write(content)

            uploader = FileUpLoader(tmp_dir)
            result = uploader.load()

            for content in files_content.values():
                assert content in result

            for filename in files_content.keys():
                assert filename in result
