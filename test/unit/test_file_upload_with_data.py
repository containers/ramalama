import os
import tempfile
from pathlib import Path

import pytest

from ramalama.file_upload.file_loader import FileUpLoader


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

        uploader = FileUpLoader(str(txt_file))
        result = uploader.load()

        assert "This is a sample text file" in result
        assert "TXTFileUpload class" in result
        assert "Special characters like: !@#$%^&*()" in result
        assert f"<!--start_document {txt_file}-->" in result

    def test_load_single_markdown_file(self, data_dir):
        """Test loading a single markdown file from the data directory."""
        md_file = data_dir / "sample.md"

        uploader = FileUpLoader(str(md_file))
        result = uploader.load()

        assert "# Sample Markdown File" in result
        assert "**Bold text** and *italic text*" in result
        assert "```python" in result
        assert "def hello_world():" in result
        assert f"<!--start_document {md_file}-->" in result

    def test_load_single_json_file(self, data_dir):
        """Test loading a single JSON file from the data directory."""
        json_file = data_dir / "sample.json"

        uploader = FileUpLoader(str(json_file))
        result = uploader.load()

        assert '"name": "test_data"' in result
        assert '"version": "1.0.0"' in result
        assert '"text_processing"' in result
        assert '"supported_formats"' in result
        assert f"<!--start_document {json_file}-->" in result

    def test_load_single_yaml_file(self, data_dir):
        """Test loading a single YAML file from the data directory."""
        yaml_file = data_dir / "sample.yaml"

        uploader = FileUpLoader(str(yaml_file))
        result = uploader.load()

        assert "name: test_config" in result
        assert "version: 1.0.0" in result
        assert "- text_processing" in result
        assert "- yaml_support" in result
        assert "deep:" in result
        assert f"<!--start_document {yaml_file}-->" in result

    def test_load_single_csv_file(self, data_dir):
        """Test loading a single CSV file from the data directory."""
        csv_file = data_dir / "sample.csv"

        uploader = FileUpLoader(str(csv_file))
        result = uploader.load()

        assert "name,age,city,occupation" in result
        assert "John Doe,30,New York,Engineer" in result
        assert "Jane Smith,25,San Francisco,Designer" in result
        assert "Bob Johnson,35,Chicago,Manager" in result
        assert f"<!--start_document {csv_file}-->" in result

    def test_load_single_toml_file(self, data_dir):
        """Test loading a single TOML file from the data directory."""
        toml_file = data_dir / "sample.toml"

        uploader = FileUpLoader(str(toml_file))
        result = uploader.load()

        assert 'name = "test_config"' in result
        assert 'version = "1.0.0"' in result
        assert 'text_processing = true' in result
        assert 'toml_support = true' in result
        assert 'with_deep_nesting = true' in result
        assert f"<!--start_document {toml_file}-->" in result

    def test_load_single_shell_script(self, data_dir):
        """Test loading a single shell script from the data directory."""
        sh_file = data_dir / "sample.sh"

        uploader = FileUpLoader(str(sh_file))
        result = uploader.load()

        assert "#!/bin/bash" in result
        assert "Hello, World! This is a test script." in result
        assert "test_function()" in result
        assert "for i in {1..3}" in result
        assert "Script completed successfully!" in result
        assert f"<!--start_document {sh_file}-->" in result

    def test_load_entire_data_directory(self, data_dir):
        """Test loading all files from the data directory."""
        uploader = FileUpLoader(str(data_dir))
        result = uploader.load()

        assert "This is a sample text file" in result  # sample.txt
        assert "# Sample Markdown File" in result  # sample.md
        assert '"name": "test_data"' in result  # sample.json
        assert "name: test_config" in result  # sample.yaml
        assert "name,age,city,occupation" in result  # sample.csv
        assert 'name = "test_config"' in result  # sample.toml
        assert "#!/bin/bash" in result  # sample.sh

        assert "<!--start_document" in result
        assert "sample.txt" in result
        assert "sample.md" in result
        assert "sample.json" in result
        assert "sample.yaml" in result
        assert "sample.csv" in result
        assert "sample.toml" in result
        assert "sample.sh" in result

    def test_file_content_integrity(self, data_dir):
        """Test that file content is preserved exactly."""
        txt_file = data_dir / "sample.txt"

        with open(txt_file, 'r') as f:
            original_content = f.read()

        uploader = FileUpLoader(str(txt_file))
        result = uploader.load()

        content_start = result.find('\n', result.find('<!--start_document')) + 1
        extracted_content = result[content_start:]

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

            uploader = FileUpLoader(tmp_dir)
            result = uploader.load()

            assert "This is a sample text file" in result  # sample.txt
            assert "# Sample Markdown File" in result  # sample.md
            assert '"name": "test_data"' in result  # sample.json

            assert "<!--start_document" in result
            assert "sample.txt" in result
            assert "sample.md" in result
            assert "sample.json" in result

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

            uploader = FileUpLoader(tmp_dir)
            result = uploader.load()

            assert "This is a sample text file" in result
            assert "This is an unsupported file type" not in result
            assert "sample.txt" in result
            assert "sample.xyz" not in result
