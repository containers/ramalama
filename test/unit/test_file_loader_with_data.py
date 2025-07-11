import os
import tempfile
from pathlib import Path

import pytest

from ramalama.file_loaders.file_manager import OpanAIChatAPIMessageBuilder


class TestFileUploadWithDataFiles:
    """Test file upload functionality using sample data files."""

    @pytest.fixture
    def data_dir(self):
        """Get the path to the test data directory."""
        current_dir = Path(__file__).parent
        return current_dir / "data" / "test_file_upload"

    def test_load_single_text_file(self, data_dir):
        """Test loading a single text file from the data directory."""
        txt_file = data_dir / "sample.txt"

        builder = OpanAIChatAPIMessageBuilder()
        messages = builder.load(str(txt_file))

        assert len(messages) == 1
        assert "This is a sample text file" in messages[0]["content"]
        assert "TXTFileUpload class" in messages[0]["content"]
        assert "Special characters like: !@#$%^&*()" in messages[0]["content"]
        assert f"<!--start_document {txt_file}-->" in messages[0]["content"]

    def test_load_single_markdown_file(self, data_dir):
        """Test loading a single markdown file from the data directory."""
        md_file = data_dir / "sample.md"

        builder = OpanAIChatAPIMessageBuilder()
        messages = builder.load(str(md_file))

        assert len(messages) == 1
        assert "# Sample Markdown File" in messages[0]["content"]
        assert "**Bold text** and *italic text*" in messages[0]["content"]
        assert "```python" in messages[0]["content"]
        assert "def hello_world():" in messages[0]["content"]
        assert f"<!--start_document {md_file}-->" in messages[0]["content"]

    def test_load_single_json_file(self, data_dir):
        """Test loading a single JSON file from the data directory."""
        json_file = data_dir / "sample.json"

        builder = OpanAIChatAPIMessageBuilder()
        messages = builder.load(str(json_file))

        assert len(messages) == 1
        assert '"name": "test_data"' in messages[0]["content"]
        assert '"version": "1.0.0"' in messages[0]["content"]
        assert '"text_processing"' in messages[0]["content"]
        assert '"supported_formats"' in messages[0]["content"]
        assert f"<!--start_document {json_file}-->" in messages[0]["content"]

    def test_load_single_yaml_file(self, data_dir):
        """Test loading a single YAML file from the data directory."""
        yaml_file = data_dir / "sample.yaml"

        builder = OpanAIChatAPIMessageBuilder()
        messages = builder.load(str(yaml_file))

        assert len(messages) == 1
        assert "name: test_config" in messages[0]["content"]
        assert "version: 1.0.0" in messages[0]["content"]
        assert "- text_processing" in messages[0]["content"]
        assert "- yaml_support" in messages[0]["content"]
        assert "deep:" in messages[0]["content"]
        assert f"<!--start_document {yaml_file}-->" in messages[0]["content"]

    def test_load_single_csv_file(self, data_dir):
        """Test loading a single CSV file from the data directory."""
        csv_file = data_dir / "sample.csv"

        builder = OpanAIChatAPIMessageBuilder()
        messages = builder.load(str(csv_file))

        assert len(messages) == 1
        assert "name,age,city,occupation" in messages[0]["content"]
        assert "John Doe,30,New York,Engineer" in messages[0]["content"]
        assert "Jane Smith,25,San Francisco,Designer" in messages[0]["content"]
        assert "Bob Johnson,35,Chicago,Manager" in messages[0]["content"]
        assert f"<!--start_document {csv_file}-->" in messages[0]["content"]

    def test_load_single_toml_file(self, data_dir):
        """Test loading a single TOML file from the data directory."""
        toml_file = data_dir / "sample.toml"

        builder = OpanAIChatAPIMessageBuilder()
        messages = builder.load(str(toml_file))

        assert len(messages) == 1
        assert 'name = "test_config"' in messages[0]["content"]
        assert 'version = "1.0.0"' in messages[0]["content"]
        assert 'text_processing = true' in messages[0]["content"]
        assert 'toml_support = true' in messages[0]["content"]
        assert 'with_deep_nesting = true' in messages[0]["content"]
        assert f"<!--start_document {toml_file}-->" in messages[0]["content"]

    def test_load_single_shell_script(self, data_dir):
        """Test loading a single shell script from the data directory."""
        sh_file = data_dir / "sample.sh"

        builder = OpanAIChatAPIMessageBuilder()
        messages = builder.load(str(sh_file))

        assert len(messages) == 1
        assert "#!/bin/bash" in messages[0]["content"]
        assert "Hello, World! This is a test script." in messages[0]["content"]
        assert "test_function()" in messages[0]["content"]
        assert "for i in {1..3}" in messages[0]["content"]
        assert "Script completed successfully!" in messages[0]["content"]
        assert f"<!--start_document {sh_file}-->" in messages[0]["content"]

    def test_load_entire_data_directory(self, data_dir):
        """Test loading all files from the data directory."""
        builder = OpanAIChatAPIMessageBuilder()
        messages = builder.load(str(data_dir))

        assert len(messages) == 1
        content = messages[0]["content"]
        assert "This is a sample text file" in content  # sample.txt
        assert "# Sample Markdown File" in content  # sample.md
        assert '"name": "test_data"' in content  # sample.json
        assert "name: test_config" in content  # sample.yaml
        assert "name,age,city,occupation" in content  # sample.csv
        assert 'name = "test_config"' in content  # sample.toml
        assert "#!/bin/bash" in content  # sample.sh

        assert "<!--start_document" in content
        assert "sample.txt" in content
        assert "sample.md" in content
        assert "sample.json" in content
        assert "sample.yaml" in content
        assert "sample.csv" in content
        assert "sample.toml" in content
        assert "sample.sh" in content

    def test_file_content_integrity(self, data_dir):
        """Test that file content is preserved exactly."""
        txt_file = data_dir / "sample.txt"

        with open(txt_file, 'r') as f:
            original_content = f.read()

        builder = OpanAIChatAPIMessageBuilder()
        messages = builder.load(str(txt_file))

        assert len(messages) == 1
        content = messages[0]["content"]
        content_start = content.find('\n', content.find('<!--start_document')) + 1
        extracted_content = content[content_start:]

        assert extracted_content == original_content

    def test_multiple_files_content_integrity(self, data_dir):
        """Test that content from multiple files is preserved correctly."""

        with tempfile.TemporaryDirectory() as tmp_dir:
            files_to_copy = ['sample.txt', 'sample.md', 'sample.json']
            for filename in files_to_copy:
                src_file = data_dir / filename
                dst_file = os.path.join(tmp_dir, filename)
                with open(src_file, 'r') as src, open(dst_file, 'w') as dst:
                    dst.write(src.read())

            builder = OpanAIChatAPIMessageBuilder()
            messages = builder.load(tmp_dir)

            assert len(messages) == 1
            content = messages[0]["content"]
            assert "This is a sample text file" in content  # sample.txt
            assert "# Sample Markdown File" in content  # sample.md
            assert '"name": "test_data"' in content  # sample.json

            assert "<!--start_document" in content
            assert "sample.txt" in content
            assert "sample.md" in content
            assert "sample.json" in content

    def test_unsupported_file_handling(self, data_dir):
        """Test that unsupported files are handled correctly."""

        with tempfile.TemporaryDirectory() as tmp_dir:
            src_file = data_dir / "sample.txt"
            dst_file = os.path.join(tmp_dir, "sample.txt")
            with open(src_file, 'r') as src, open(dst_file, 'w') as dst:
                dst.write(src.read())

            unsupported_file = os.path.join(tmp_dir, "sample.xyz")
            with open(unsupported_file, 'w') as f:
                f.write("This is an unsupported file type")

            builder = OpanAIChatAPIMessageBuilder()
            messages = builder.load(tmp_dir)

            assert len(messages) == 1
            content = messages[0]["content"]
            assert "This is a sample text file" in content
            assert "This is an unsupported file type" not in content
            assert "sample.txt" in content
            assert "sample.xyz" not in content


class TestImageUploadWithDataFiles:
    """Test image upload functionality using sample data files."""

    @pytest.fixture
    def data_dir(self):
        """Get the path to the test data directory."""
        current_dir = Path(__file__).parent
        return current_dir / "data" / "test_file_upload"

    def test_load_single_image_file(self, data_dir):
        """Test loading a single image file."""
        with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp_file:
            with open(tmp_file.name, "wb") as f:
                f.write(b"fake image data for testing")

            builder = OpanAIChatAPIMessageBuilder()
            messages = builder.load(tmp_file.name)

            assert len(messages) == 1
            assert isinstance(messages[0]["content"], list)
            assert len(messages[0]["content"]) == 1
            assert 'image_url' in messages[0]["content"][0]
            assert 'url' in messages[0]["content"][0]["image_url"]
            assert "data:image/" in messages[0]["content"][0]["image_url"]["url"]
            assert "base64," in messages[0]["content"][0]["image_url"]["url"]

    def test_load_multiple_image_files(self, data_dir):
        """Test loading multiple image files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            jpg_file = os.path.join(tmp_dir, "test1.jpg")
            with open(jpg_file, "wb") as f:
                f.write(b"jpg image data")

            png_file = os.path.join(tmp_dir, "test2.png")
            with open(png_file, "wb") as f:
                f.write(b"png image data")

            gif_file = os.path.join(tmp_dir, "test3.gif")
            with open(gif_file, "wb") as f:
                f.write(b"gif image data")

            builder = OpanAIChatAPIMessageBuilder()
            messages = builder.load(tmp_dir)

            assert len(messages) == 1
            assert isinstance(messages[0]["content"], list)
            assert len(messages[0]["content"]) == 3
            assert all('image_url' in item for item in messages[0]["content"])
            assert all('url' in item["image_url"] for item in messages[0]["content"])
            assert all("data:image/" in item["image_url"]["url"] for item in messages[0]["content"])
            assert all("base64," in item["image_url"]["url"] for item in messages[0]["content"])

    def test_image_file_content_integrity(self, data_dir):
        """Test that image file content is preserved exactly."""
        with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp_file:
            original_data = b"fake image data for integrity test"
            with open(tmp_file.name, "wb") as f:
                f.write(original_data)

            builder = OpanAIChatAPIMessageBuilder()
            messages = builder.load(tmp_file.name)

            assert len(messages) == 1
            assert isinstance(messages[0]["content"], list)
            assert len(messages[0]["content"]) == 1

            # Extract base64 data from result
            url = messages[0]["content"][0]["image_url"]["url"]
            base64_data = url.split("base64,")[1]
            import base64

            decoded_data = base64.b64decode(base64_data)
            assert decoded_data == original_data

    def test_mixed_image_formats(self, data_dir):
        """Test loading images with different formats."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            image_files = {
                "test.jpg": b"jpeg data",
                "test.png": b"png data",
                "test.gif": b"gif data",
                "test.bmp": b"bmp data",
                "test.webp": b"webp data",
                "test.ico": b"ico data",
                "test.tiff": b"tiff data",
                "test.tif": b"tif data",
            }

            for filename, data in image_files.items():
                file_path = os.path.join(tmp_dir, filename)
                with open(file_path, "wb") as f:
                    f.write(data)

            builder = OpanAIChatAPIMessageBuilder()
            messages = builder.load(tmp_dir)

            assert len(messages) == 1
            assert isinstance(messages[0]["content"], list)
            assert len(messages[0]["content"]) == 8
            assert all('image_url' in item for item in messages[0]["content"])
            assert all('url' in item["image_url"] for item in messages[0]["content"])
            assert all("data:image/" in item["image_url"]["url"] for item in messages[0]["content"])
            assert all("base64," in item["image_url"]["url"] for item in messages[0]["content"])

    def test_image_unsupported_file_handling(self, data_dir):
        """Test that unsupported image files are handled correctly."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            jpg_file = os.path.join(tmp_dir, "test.jpg")
            with open(jpg_file, "wb") as f:
                f.write(b"Supported image data")

            unsupported_file = os.path.join(tmp_dir, "test.xyz")
            with open(unsupported_file, "wb") as f:
                f.write(b"Unsupported image data")

            builder = OpanAIChatAPIMessageBuilder()
            messages = builder.load(tmp_dir)

            assert len(messages) == 1
            assert isinstance(messages[0]["content"], list)
            assert len(messages[0]["content"]) == 1
            assert 'image_url' in messages[0]["content"][0]
            assert 'url' in messages[0]["content"][0]["image_url"]
            assert "data:image/" in messages[0]["content"][0]["image_url"]["url"]
            assert "base64," in messages[0]["content"][0]["image_url"]["url"]

    def test_image_case_insensitive_extensions(self, data_dir):
        """Test that image file extensions are handled case-insensitively."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            image_files = {
                "test.JPG": b"uppercase jpg",
                "test.PNG": b"uppercase png",
                "test.GIF": b"uppercase gif",
                "test.BMP": b"uppercase bmp",
                "test.WEBP": b"uppercase webp",
                "test.ICO": b"uppercase ico",
                "test.TIFF": b"uppercase tiff",
                "test.TIF": b"uppercase tif",
            }

            for filename, data in image_files.items():
                file_path = os.path.join(tmp_dir, filename)
                with open(file_path, "wb") as f:
                    f.write(data)

            builder = OpanAIChatAPIMessageBuilder()
            messages = builder.load(tmp_dir)

            assert len(messages) == 1
            assert isinstance(messages[0]["content"], list)
            assert len(messages[0]["content"]) == 8
            assert all('image_url' in item for item in messages[0]["content"])
            assert all('url' in item["image_url"] for item in messages[0]["content"])
            assert all("data:image/" in item["image_url"]["url"] for item in messages[0]["content"])
            assert all("base64," in item["image_url"]["url"] for item in messages[0]["content"])
