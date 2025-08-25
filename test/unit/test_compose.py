# tests/test_compose.py

from pathlib import Path

import pytest

from ramalama.compose import Compose, genfile


class Args:
    def __init__(
        self, name: str = "", rag: str = "", port: str = "", env: list = None, image: str = "test-image/ramalama:latest"
    ):
        self.name = name
        self.rag = rag
        self.env = env if env is not None else []
        if port:
            self.port = port
        self.image = image


class Input:
    def __init__(
        self,
        model_name: str = "",
        model_src_path: str = "",
        model_dest_path: str = "",
        model_file_exists: bool = True,
        chat_template_src_path: str = "",
        chat_template_dest_path: str = "",
        chat_template_file_exists: bool = False,
        mmproj_src_path: str = "",
        mmproj_dest_path: str = "",
        mmproj_file_exists: bool = False,
        args: Args = Args(),
        exec_args: list = None,
    ):
        self.model_name = model_name
        self.model_src_path = model_src_path
        self.model_dest_path = model_dest_path
        self.model_file_exists = model_file_exists
        self.chat_template_src_path = chat_template_src_path
        self.chat_template_dest_path = chat_template_dest_path
        self.chat_template_file_exists = chat_template_file_exists
        self.mmproj_src_path = mmproj_src_path
        self.mmproj_dest_path = mmproj_dest_path
        self.mmproj_file_exists = mmproj_file_exists
        self.args = args
        self.exec_args = exec_args if exec_args is not None else []


DATA_PATH = Path(__file__).parent / "data" / "test_compose"


@pytest.mark.parametrize(
    "input_data,expected_file_name",
    [
        (
            Input(
                model_name="tinyllama",
                model_src_path="/models/tinyllama.gguf",
                model_dest_path="/mnt/models/tinyllama.gguf",
                exec_args=["llama-server", "--model", "/mnt/models/tinyllama.gguf"],
            ),
            "basic.yaml",
        ),
        (
            Input(
                model_name="tinyllama",
                model_src_path="/models/tinyllama.gguf",
                model_dest_path="/mnt/models/tinyllama.gguf",
                args=Args(port="9090"),
                exec_args=["llama-server"],
            ),
            "with_port.yaml",
        ),
        (
            Input(
                model_name="tinyllama",
                model_src_path="/models/tinyllama.gguf",
                model_dest_path="/mnt/models/tinyllama.gguf",
                args=Args(port="8080:9090"),
                exec_args=["llama-server"],
            ),
            "with_port_mapping.yaml",
        ),
        (
            Input(
                model_name="granite",
                model_src_path="/models/granite.gguf",
                model_dest_path="/mnt/models/granite.gguf",
                args=Args(rag="oci:quay.io/my-org/my-rag-data:latest"),
            ),
            "with_rag_oci.yaml",
        ),
        (
            Input(
                model_name="granite",
                model_src_path="/models/granite.gguf",
                model_dest_path="/mnt/models/granite.gguf",
                args=Args(rag="/data/rag_files"),
            ),
            "with_rag_path.yaml",
        ),
        (
            Input(
                model_name="tinyllama",
                model_src_path="/models/tinyllama.gguf",
                model_dest_path="/mnt/models/tinyllama.gguf",
                args=Args(name="my-custom-api-name"),
            ),
            "with_custom_name.yaml",
        ),
        (
            Input(
                model_name="tinyllama",
                model_src_path="/models/tinyllama.gguf",
                model_dest_path="/mnt/models/tinyllama.gguf",
                chat_template_src_path="/templates/chat.json",
                chat_template_dest_path="/mnt/templates/chat.json",
                chat_template_file_exists=True,
            ),
            "with_chat_template.yaml",
        ),
        (
            Input(
                model_name="llava",
                model_src_path="/models/llava.gguf",
                model_dest_path="/mnt/models/llava.gguf",
                mmproj_src_path="/models/llava.mmproj",
                mmproj_dest_path="/mnt/models/llava.mmproj",
                mmproj_file_exists=True,
            ),
            "with_mmproj.yaml",
        ),
        (
            Input(
                model_name="gemma-cuda",
                model_src_path="/models/gemma.gguf",
                model_dest_path="/mnt/models/gemma.gguf",
                args=Args(image="test-image/cuda:latest"),
            ),
            "with_nvidia_gpu.yaml",
        ),
        (
            Input(
                model_name="tinyllama",
                model_src_path="/models/tinyllama.gguf",
                model_dest_path="/mnt/models/tinyllama.gguf",
                args=Args(env=["LOG_LEVEL=debug", "THREADS=8"]),
            ),
            "with_env_vars.yaml",
        ),
    ],
)
def test_compose_generate(input_data: Input, expected_file_name: str, monkeypatch):
    """Test the Compose.generate() method with various configurations."""

    expected_file_path = DATA_PATH / expected_file_name
    expected_content = expected_file_path.read_text()

    existence = {
        input_data.model_src_path: input_data.model_file_exists,
        input_data.chat_template_src_path: input_data.chat_template_file_exists,
        input_data.mmproj_src_path: input_data.mmproj_file_exists,
        "/data/rag_files": True,
        "/dev/dri": True,
        "/dev/kfd": True,
        "/dev/accel": True,
    }
    monkeypatch.setattr("os.path.exists", lambda path: existence.get(path, False))

    monkeypatch.setattr("ramalama.compose.get_accel_env_vars", lambda: {"ACCEL_ENV": "true"})
    monkeypatch.setattr("ramalama.compose.version", lambda: "0.1.0-test")

    compose_generator = Compose(
        model_name=input_data.model_name,
        model_paths=(input_data.model_src_path, input_data.model_dest_path),
        chat_template_paths=(input_data.chat_template_src_path, input_data.chat_template_dest_path),
        mmproj_paths=(input_data.mmproj_src_path, input_data.mmproj_dest_path),
        args=input_data.args,
        exec_args=input_data.exec_args,
    )

    generated_file = compose_generator.generate()
    generated_content = generated_file.content

    assert generated_content.strip() == expected_content.strip()


def test_compose_genfile(monkeypatch):
    """Test the standalone genfile helper function."""
    printed_output = []
    monkeypatch.setattr("builtins.print", lambda x: printed_output.append(x))

    name = "test-service"
    content = "services:\n  test-service:\n    image: hello-world"

    result = genfile(name, content)

    assert result.filename == "docker-compose.yaml"
    assert result.content == content
    assert printed_output == ["Generating Docker Compose file: docker-compose.yaml"]


def test_genfile_empty_content(monkeypatch):
    """Test genfile with empty content."""
    printed_output = []
    monkeypatch.setattr("builtins.print", lambda x: printed_output.append(x))

    name = "empty-service"
    content = ""

    result = genfile(name, content)

    assert result.filename == "docker-compose.yaml"
    assert result.content == ""
    assert printed_output == ["Generating Docker Compose file: docker-compose.yaml"]


def test_compose_no_port_arg(monkeypatch):
    """Test Compose generation when the args object has no 'port' attribute."""

    class ArgsNoPort:
        def __init__(self):
            self.image = "test-image"
            self.rag = ""
            self.env = []
            self.name = "no-port-test"

    args = ArgsNoPort()
    monkeypatch.setattr("os.path.exists", lambda path: False)
    monkeypatch.setattr("ramalama.compose.get_accel_env_vars", lambda: {})
    monkeypatch.setattr("ramalama.compose.version", lambda: "test")

    compose = Compose("test", ("/a", "/b"), None, None, args, [])
    result = compose.generate().content

    assert 'ports:\n      - "8080:8080"' in result


def test_compose_no_env_vars(monkeypatch):
    """Test Compose generation when no environment variables are set."""
    monkeypatch.setattr("os.path.exists", lambda path: False)
    monkeypatch.setattr("ramalama.compose.get_accel_env_vars", lambda: {})
    monkeypatch.setattr("ramalama.compose.version", lambda: "test")

    args = Args()
    compose = Compose("test", ("/a", "/b"), None, None, args, [])
    result = compose.generate().content

    assert "environment:" not in result


def test_compose_no_devices(monkeypatch):
    """Test Compose generation when no host devices are found."""
    monkeypatch.setattr("os.path.exists", lambda path: False)
    monkeypatch.setattr("ramalama.compose.get_accel_env_vars", lambda: {})
    monkeypatch.setattr("ramalama.compose.version", lambda: "test")

    args = Args()
    compose = Compose("test", ("/a", "/b"), None, None, args, [])
    result = compose.generate().content

    assert "devices:" not in result
