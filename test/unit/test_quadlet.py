import io
import os
from pathlib import Path

import pytest

from ramalama.quadlet import Quadlet


class Args:
    def __init__(self, name: str = "", rag: str = "", env: list = []):
        self.name = name
        self.rag = rag
        self.env = env


class Input:

    def __init__(
        self, model: str = "", chat_template: str = "", image: str = "", args: Args = Args(), exec_args: list = []
    ):
        self.model = model
        self.chat_template = chat_template
        self.image = image
        self.args = args
        self.exec_args = exec_args


DATA_PATH = Path(__file__).parent / "data" / "test_quadlet"


@pytest.mark.parametrize(
    "input,expected_files_path",
    [
        (Input(model="tinyllama"), DATA_PATH / "empty"),
        (Input(model="tinyllama", image="testimage"), DATA_PATH / "basic"),
    ],
)
def test_quadlet_generate(input: Input, expected_files_path: Path):
    expected_files = dict()
    for file in os.listdir(expected_files_path):
        with open(os.path.join(expected_files_path, file)) as f:
            expected_files[file] = f.read()

    for file in Quadlet(input.model, input.chat_template, input.image, input.args, input.exec_args).generate():
        assert file.filename in expected_files

        with io.StringIO() as sio:
            file.config.write(sio)
            sio.seek(0)  # rewind

            assert expected_files[file.filename] == sio.read()
            del expected_files[file.filename]

    assert expected_files == dict()
