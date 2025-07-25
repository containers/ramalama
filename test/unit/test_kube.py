from pathlib import Path
from typing import Optional

import pytest

from ramalama.kube import Kube


class Args:
    def __init__(self, name: str = "", rag: str = "", port: str = "", env: list = None, MODEL: Optional[str] = None):
        self.name = name
        self.rag = rag
        self.env = env if env is not None else []
        if port:  # Only set port attribute if port is provided
            self.port = port
        self.image = "testimage"
        if MODEL is not None:
            self.MODEL = MODEL


class Input:
    def __init__(
        self,
        model_name: str = "",
        model_src_path: str = "",
        model_dest_path: str = "",
        model_file_exists: bool = False,
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


DATA_PATH = Path(__file__).parent / "data" / "test_kube"


@pytest.mark.parametrize(
    "input,expected_file_name",
    [
        (
            Input(
                model_name="tinyllama",
                model_src_path="/path/to/model.file",
                model_dest_path="/mnt/models/model.file",
                model_file_exists=True,
                exec_args=["llama-server", "--model", "/mnt/models/model.file"],
            ),
            "basic_hostpath.yaml",
        ),
        (
            Input(
                model_name="tinyllama",
                model_src_path="/path/to/model.file",
                model_dest_path="/mnt/models/model.file",
                model_file_exists=True,
                args=Args(port="8080"),
                exec_args=["llama-server", "--model", "/mnt/models/model.file"],
            ),
            "with_port.yaml",
        ),
        (
            Input(
                model_name="tinyllama",
                model_src_path="/path/to/model.file",
                model_dest_path="/mnt/models/model.file",
                model_file_exists=True,
                args=Args(port="8080:3000"),
                exec_args=["llama-server", "--model", "/mnt/models/model.file"],
            ),
            "with_port_mapping.yaml",
        ),
        (
            Input(
                model_name="tinyllama",
                model_src_path="/path/to/model.file",
                model_dest_path="/mnt/models/model.file",
                model_file_exists=True,
                args=Args(rag="registry.redhat.io/ubi9/ubi:latest"),
                exec_args=["llama-server", "--model", "/mnt/models/model.file"],
            ),
            "with_rag.yaml",
        ),
        (
            Input(
                model_name="tinyllama",
                model_src_path="/path/to/model.file",
                model_dest_path="/mnt/models/model.file",
                model_file_exists=True,
                args=Args(name="custom-name"),
                exec_args=["llama-server", "--model", "/mnt/models/model.file"],
            ),
            "with_custom_name.yaml",
        ),
        (
            Input(
                model_name="tinyllama",
                model_src_path="/path/to/model.file",
                model_dest_path="/mnt/models/model.file",
                model_file_exists=True,
                chat_template_src_path="/path/to/chat_template",
                chat_template_dest_path="/mnt/models/chat_template",
                chat_template_file_exists=True,
                exec_args=["llama-server", "--model", "/mnt/models/model.file"],
            ),
            "with_chat_template.yaml",
        ),
        (
            Input(
                model_name="tinyllama",
                model_src_path="/path/to/model.file",
                model_dest_path="/mnt/models/model.file",
                model_file_exists=True,
                mmproj_src_path="/path/to/mmproj",
                mmproj_dest_path="/mnt/models/mmproj",
                mmproj_file_exists=True,
                exec_args=["llama-server", "--model", "/mnt/models/model.file"],
            ),
            "with_mmproj.yaml",
        ),
    ],
)
def test_kube_generate(input: Input, expected_file_name: str, monkeypatch):
    """Test the Kube.generate() method with various configurations."""

    # Read expected output
    expected_file_path = DATA_PATH / expected_file_name
    expected_content = Path(expected_file_path).read_text()

    existence = {
        input.model_src_path: input.model_file_exists,
        input.chat_template_src_path: input.chat_template_file_exists,
        input.mmproj_src_path: input.mmproj_file_exists,
        "/dev/dri": True,
        "/dev/kfd": True,
    }

    monkeypatch.setattr("os.path.exists", lambda path: existence.get(path, False))

    # Mock environment variables
    monkeypatch.setattr("ramalama.kube.get_accel_env_vars", lambda: {"TEST_ENV": "test_value"})

    # Mock version
    monkeypatch.setattr("ramalama.kube.version", lambda: "test-version")

    # Mock genname to return predictable name
    if not input.args.name:
        monkeypatch.setattr("ramalama.kube.genname", lambda: "generated-name")

    # Create Kube instance and generate
    chat_template_paths = None
    if input.chat_template_src_path:
        chat_template_paths = (input.chat_template_src_path, input.chat_template_dest_path)

    mmproj_paths = None
    if input.mmproj_src_path:
        mmproj_paths = (input.mmproj_src_path, input.mmproj_dest_path)

    kube = Kube(
        input.model_name,
        (input.model_src_path, input.model_dest_path),
        chat_template_paths,
        mmproj_paths,
        input.args,
        input.exec_args,
    )

    generated_file = kube.generate()

    # Compare generated content
    generated_content = generated_file.content
    assert generated_content == expected_content


def test_kube_genfile(monkeypatch):
    """Test the genfile function."""
    from ramalama.kube import genfile

    # Capture print output
    printed_output = []
    monkeypatch.setattr("builtins.print", lambda x: printed_output.append(x))

    name = "test-model"
    content = "test yaml content"

    result = genfile(name, content)

    assert result.filename == "test-model.yaml"
    assert result.content == content
    assert printed_output == ["Generating Kubernetes YAML file: test-model.yaml"]


def test_kube_no_port(monkeypatch):
    """Test Kube generation when args has no port attribute."""

    class ArgsNoPort:
        def __init__(self):
            self.image = "testimage"
            self.rag = ""

    args = ArgsNoPort()

    monkeypatch.setattr("os.path.exists", lambda path: False)
    monkeypatch.setattr("ramalama.kube.get_accel_env_vars", lambda: {})
    monkeypatch.setattr("ramalama.kube.version", lambda: "test-version")
    monkeypatch.setattr("ramalama.kube.genname", lambda: "test-name")

    kube = Kube(
        "test-model",
        ("/path/to/model", "model"),
        None,
        None,
        args,
        ["llama-server"],
    )

    result = kube.generate()

    # Should generate without port section
    content = result.content
    assert "ports:" not in content
    assert "containerPort:" not in content


def test_kube_no_env_vars(monkeypatch):
    """Test Kube generation when no environment variables are available."""

    monkeypatch.setattr("os.path.exists", lambda path: False)
    monkeypatch.setattr("ramalama.kube.get_accel_env_vars", lambda: {})
    monkeypatch.setattr("ramalama.kube.version", lambda: "test-version")
    monkeypatch.setattr("ramalama.kube.genname", lambda: "test-name")

    args = Args()

    kube = Kube(
        "test-model",
        ("/path/to/model", "model"),
        None,
        None,
        args,
        ["llama-server"],
    )

    result = kube.generate()

    # Should generate without env section
    content = result.content
    assert "env:" not in content
    assert "- name: TEST_ENV" not in content  # More specific check for env variables


def test_kube_no_devices(monkeypatch):
    """Test Kube generation when no GPU devices are available."""

    monkeypatch.setattr("os.path.exists", lambda path: path not in ["/dev/dri", "/dev/kfd"])
    monkeypatch.setattr("ramalama.kube.get_accel_env_vars", lambda: {})
    monkeypatch.setattr("ramalama.kube.version", lambda: "test-version")
    monkeypatch.setattr("ramalama.kube.genname", lambda: "test-name")

    args = Args()

    kube = Kube(
        "test-model",
        ("/path/to/model", "model"),
        None,
        None,
        args,
        ["llama-server"],
    )

    result = kube.generate()

    # Should still have model volume but no device volumes
    content = result.content
    assert "name: model" in content
    assert "name: dri" not in content
    assert "name: kfd" not in content
