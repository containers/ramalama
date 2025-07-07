import os
import tempfile
from unittest.mock import mock_open, patch

import pytest

from ramalama.file_loaders.file_manager import ImageFileManager, OpanAIChatAPIMessageBuilder, TextFileManager
from ramalama.file_loaders.file_types.base import BaseFileLoader
from ramalama.file_loaders.file_types.image import BasicImageFileLoader
from ramalama.file_loaders.file_types.txt import TXTFileLoader


class TestBaseFileLoader:
    """Test the abstract base class for file upload handlers."""

    def test_base_file_loader_is_abstract(self):
        """Test that BaseFileLoader is an abstract class."""
        # BaseFileLoader is an abstract class with static methods, so it can't be instantiated
        # but we can test that it has the required abstract methods
        assert hasattr(BaseFileLoader, 'load')
        assert hasattr(BaseFileLoader, 'file_extensions')


class TestTXTFileLoader:
    """Test the text file upload handler."""

    def test_txt_file_loader_file_extensions(self):
        """Test that TXTFileLoader supports correct file extensions."""
        extensions = TXTFileLoader.file_extensions()
        expected_extensions = {".txt", ".sh", ".md", ".yaml", ".yml", ".json", ".csv", ".toml"}
        assert extensions == expected_extensions

    def test_txt_file_loader_load_content(self):
        """Test loading content from a text file."""
        test_content = "This is test content\nwith multiple lines."

        with patch("builtins.open", mock_open(read_data=test_content)):
            result = TXTFileLoader.load("/path/to/test.txt")

        assert result == test_content

    def test_txt_file_loader_load_empty_file(self):
        """Test loading content from an empty text file."""
        with patch("builtins.open", mock_open(read_data="")):
            result = TXTFileLoader.load("/path/to/empty.txt")

        assert result == ""

    def test_txt_file_loader_load_unicode_content(self):
        """Test loading Unicode content from a text file."""
        test_content = "Hello 世界! 🌍\nUnicode test: éñü"

        with patch("builtins.open", mock_open(read_data=test_content)):
            result = TXTFileLoader.load("/path/to/unicode.txt")

        assert result == test_content


class TestTextFileManager:
    """Test the text file manager class."""

    def test_text_file_manager_initialization(self):
        """Test that TextFileManager can be initialized."""
        manager = TextFileManager()
        assert manager.document_delimiter is not None

    def test_text_file_manager_initialization_custom_delimiter(self):
        """Test that TextFileManager can be initialized with custom delimiter."""
        custom_delimiter = "---START $name---"
        manager = TextFileManager(delim_string=custom_delimiter)
        assert manager.document_delimiter.template == custom_delimiter

    def test_text_file_manager_load_single_file(self):
        """Test loading a single file."""
        with patch.object(TXTFileLoader, 'load', return_value="Test content"):
            manager = TextFileManager()
            result = manager.load(["test.txt"])

        expected = "\n<!--start_document test.txt-->\nTest content"
        assert result == expected

    def test_text_file_manager_load_multiple_files(self):
        """Test loading multiple files."""
        with patch.object(TXTFileLoader, 'load', side_effect=["Content 1", "Content 2"]):
            manager = TextFileManager()
            result = manager.load(["test1.txt", "test2.txt"])

        expected = "\n<!--start_document test1.txt-->\nContent 1\n<!--start_document test2.txt-->\nContent 2"
        assert result == expected

    def test_text_file_manager_load_empty_file_list(self):
        """Test loading with empty file list."""
        manager = TextFileManager()
        result = manager.load([])

        assert result == ""

    def test_text_file_manager_get_loaders(self):
        """Test that get_loaders returns correct loaders."""
        loaders = TextFileManager.get_loaders()
        assert TXTFileLoader in loaders


class TestBasicImageFileLoader:
    """Test the basic image file upload handler."""

    def test_basic_image_file_loader_file_extensions(self):
        """Test that BasicImageFileLoader supports correct file extensions."""
        extensions = BasicImageFileLoader.file_extensions()
        expected_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".ico"}
        assert extensions == expected_extensions

    def test_basic_image_file_loader_load_content(self):
        """Test loading content from an image file."""
        test_image_data = b"fake image data"
        expected_base64 = "ZmFrZSBpbWFnZSBkYXRh"  # base64 of "fake image data"

        with patch("builtins.open", mock_open(read_data=test_image_data)):
            with patch("mimetypes.guess_type", return_value=("image/jpeg", None)):
                result = BasicImageFileLoader.load("/path/to/test.jpg")

        expected = f"data:image/jpeg;base64,{expected_base64}"
        assert result == expected

    def test_basic_image_file_loader_load_with_unknown_mime_type(self):
        """Test loading content from an image file with unknown mime type."""
        test_image_data = b"fake image data"
        expected_base64 = "ZmFrZSBpbWFnZSBkYXRh"

        with patch("builtins.open", mock_open(read_data=test_image_data)):
            with patch("mimetypes.guess_type", return_value=(None, None)):
                result = BasicImageFileLoader.load("/path/to/test.jpg")

        expected = f"data:None;base64,{expected_base64}"
        assert result == expected


class TestImageFileManager:
    """Test the image file manager class."""

    def test_image_file_manager_load_single_image_file(self):
        """Test loading a single image file."""
        with patch.object(BasicImageFileLoader, 'load', return_value="data:image/jpeg;base64,test"):
            manager = ImageFileManager()
            result = manager.load(["test.jpg"])

        assert len(result) == 1
        assert result[0] == "data:image/jpeg;base64,test"

    def test_image_file_manager_load_empty_file_list(self):
        """Test loading with empty file list."""
        manager = ImageFileManager()
        result = manager.load([])

        assert result == []

    def test_image_file_manager_get_loaders(self):
        """Test that get_loaders returns correct loaders."""
        loaders = ImageFileManager.get_loaders()
        assert BasicImageFileLoader in loaders

    def test_image_file_manager_load_multiple_images(self):
        """Test loading multiple image files."""
        with patch.object(
            BasicImageFileLoader, 'load', side_effect=["data:image/jpeg;base64,test1", "data:image/png;base64,test2"]
        ):
            manager = ImageFileManager()
            result = manager.load(["test1.jpg", "test2.png"])

        assert len(result) == 2
        assert result[0] == "data:image/jpeg;base64,test1"
        assert result[1] == "data:image/png;base64,test2"

    def test_image_file_manager_load_unsupported_extension(self):
        """Test that unsupported file extensions are handled properly."""
        # Patch the loader so it would raise an error if called with an unsupported extension
        with patch.object(BasicImageFileLoader, 'load'):
            manager = ImageFileManager()
            with pytest.raises(ValueError, match="Unsupported file type: .txt"):
                manager.load(["test.txt", "test.jpg"])


class TestOpanAIChatAPIMessageBuilder:
    """Test the main API message builder class."""

    def test_builder_initialization(self):
        """Test that OpanAIChatAPIMessageBuilder can be initialized."""
        builder = OpanAIChatAPIMessageBuilder()
        assert hasattr(builder, 'text_manager')
        assert hasattr(builder, 'image_manager')

    def test_builder_partition_files_single_text_file(self):
        """Test partitioning a single text file."""
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_file:
            with open(tmp_file.name, "w") as f:
                f.write("Test content")

            builder = OpanAIChatAPIMessageBuilder()
            text_files, image_files, unsupported_files = builder.partition_files(tmp_file.name)

            assert len(text_files) == 1
            assert text_files[0] == tmp_file.name
            assert len(image_files) == 0
            assert len(unsupported_files) == 0

    def test_builder_partition_files_single_image_file(self):
        """Test partitioning a single image file."""
        with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp_file:
            with open(tmp_file.name, "wb") as f:
                f.write(b"fake image data")

            builder = OpanAIChatAPIMessageBuilder()
            text_files, image_files, unsupported_files = builder.partition_files(tmp_file.name)

            assert len(text_files) == 0
            assert len(image_files) == 1
            assert image_files[0] == tmp_file.name
            assert len(unsupported_files) == 0

    def test_builder_partition_files_directory(self):
        """Test partitioning files in a directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            txt_file = os.path.join(tmp_dir, "test.txt")
            with open(txt_file, "w") as f:
                f.write("Text content")

            jpg_file = os.path.join(tmp_dir, "test.jpg")
            with open(jpg_file, "wb") as f:
                f.write(b"image data")

            unsupported_file = os.path.join(tmp_dir, "test.xyz")
            with open(unsupported_file, "w") as f:
                f.write("Unsupported content")

            builder = OpanAIChatAPIMessageBuilder()
            text_files, image_files, unsupported_files = builder.partition_files(tmp_dir)

            assert len(text_files) == 1
            assert txt_file in text_files
            assert len(image_files) == 1
            assert jpg_file in image_files
            assert len(unsupported_files) == 1
            assert unsupported_file in unsupported_files

    def test_builder_partition_files_nonexistent_file(self):
        """Test partitioning a non-existent file."""
        builder = OpanAIChatAPIMessageBuilder()
        with pytest.raises(ValueError, match="does not exist"):
            builder.partition_files("/nonexistent/file.txt")

    def test_builder_supported_extensions(self):
        """Test that supported_extensions returns correct extensions."""
        builder = OpanAIChatAPIMessageBuilder()
        extensions = builder.supported_extensions()

        # Should include both text and image extensions
        assert '.txt' in extensions
        assert '.jpg' in extensions
        assert '.png' in extensions
        assert '.md' in extensions

    def test_builder_load_text_files_only(self):
        """Test loading only text files."""
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp_file:
            with open(tmp_file.name, "w") as f:
                f.write("Test content")

            builder = OpanAIChatAPIMessageBuilder()
            messages = builder.load(tmp_file.name)

            assert len(messages) == 1
            assert messages[0]["role"] == "system"
            assert "Test content" in messages[0]["content"]
            assert f"<!--start_document {tmp_file.name}-->" in messages[0]["content"]

    def test_builder_load_image_files_only(self):
        """Test loading only image files."""
        with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp_file:
            with open(tmp_file.name, "wb") as f:
                f.write(b"fake image data")

            builder = OpanAIChatAPIMessageBuilder()
            messages = builder.load(tmp_file.name)

            assert len(messages) == 1
            assert messages[0]["role"] == "system"
            assert isinstance(messages[0]["content"], list)
            assert len(messages[0]["content"]) == 1
            assert 'image_url' in messages[0]["content"][0]
            assert 'url' in messages[0]["content"][0]["image_url"]
            assert "data:image/" in messages[0]["content"][0]["image_url"]["url"]

    def test_builder_load_mixed_files(self):
        """Test loading mixed text and image files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            txt_file = os.path.join(tmp_dir, "test.txt")
            with open(txt_file, "w") as f:
                f.write("Text content")

            jpg_file = os.path.join(tmp_dir, "test.jpg")
            with open(jpg_file, "wb") as f:
                f.write(b"image data")

            builder = OpanAIChatAPIMessageBuilder()
            messages = builder.load(tmp_dir)

            assert len(messages) == 2
            # First message should be text
            assert messages[0]["role"] == "system"
            assert "Text content" in messages[0]["content"]
            # Second message should be image
            assert messages[1]["role"] == "system"
            assert isinstance(messages[1]["content"], list)
            assert len(messages[1]["content"]) == 1

    def test_builder_load_no_supported_files(self):
        """Test loading directory with no supported files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            unsupported_file = os.path.join(tmp_dir, "test.xyz")
            with open(unsupported_file, "w") as f:
                f.write("Unsupported content")

            builder = OpanAIChatAPIMessageBuilder()
            messages = builder.load(tmp_dir)

            assert len(messages) == 0

    def test_builder_load_case_insensitive_extensions(self):
        """Test that file extensions are handled case-insensitively."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            txt_file = os.path.join(tmp_dir, "test.TXT")
            with open(txt_file, "w") as f:
                f.write("Uppercase extension")

            jpg_file = os.path.join(tmp_dir, "test.JPG")
            with open(jpg_file, "wb") as f:
                f.write(b"Uppercase image")

            builder = OpanAIChatAPIMessageBuilder()
            text_files, image_files, unsupported_files = builder.partition_files(tmp_dir)

            assert len(text_files) == 1
            assert txt_file in text_files
            assert len(image_files) == 1
            assert jpg_file in image_files
            assert len(unsupported_files) == 0


class TestSupportedExtensions:
    """Test the supported extensions mapping."""

    def test_text_manager_supported_extensions(self):
        """Test that TextFileManager supports correct extensions."""
        manager = TextFileManager()
        supported_extensions = manager.loaders.keys()

        assert '.txt' in supported_extensions
        assert '.sh' in supported_extensions
        assert '.md' in supported_extensions
        assert '.yaml' in supported_extensions
        assert '.yml' in supported_extensions
        assert '.json' in supported_extensions
        assert '.csv' in supported_extensions
        assert '.toml' in supported_extensions

    def test_image_manager_supported_extensions(self):
        """Test that ImageFileManager supports correct extensions."""
        manager = ImageFileManager()
        supported_extensions = manager.loaders.keys()

        assert '.jpg' in supported_extensions
        assert '.jpeg' in supported_extensions
        assert '.png' in supported_extensions
        assert '.gif' in supported_extensions
        assert '.bmp' in supported_extensions
        assert '.tiff' in supported_extensions
        assert '.tif' in supported_extensions
        assert '.webp' in supported_extensions
        assert '.ico' in supported_extensions


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

            builder = OpanAIChatAPIMessageBuilder()
            messages = builder.load(tmp_dir)

            assert len(messages) == 1
            content = messages[0]["content"]
            for file_content in files_content.values():
                assert file_content in content

            for filename in files_content.keys():
                assert filename in content
