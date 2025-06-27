import io
import os
from pathlib import Path
from typing import Optional

import pytest

from ramalama.quadlet import Quadlet


class Args:
    def __init__(self, name: str = "", rag: str = "", port: str = "", env: list = [], MODEL: Optional[str] = None):
        self.name = name
        self.rag = rag
        self.env = env
        self.port = port
        self.image = "testimage"
        if MODEL is not None:
            self.MODEL = MODEL


class Input:

    def __init__(
        self,
        model: str = "",
        model_file_exists: bool = False,
        chat_template: str = "",
        chat_template_file_exists: bool = False,
        image: str = "",
        args: Args = Args(),
        exec_args: list = [],
    ):
        self.model = model
        self.model_file_exists = model_file_exists
        self.chat_template = chat_template
        self.chat_template_file_exists = chat_template_file_exists
        self.image = image
        self.args = args
        self.exec_args = exec_args


DATA_PATH = Path(__file__).parent / "data" / "test_quadlet"


@pytest.mark.parametrize(
    "input,expected_files_path",
    [
        (Input(model="tinyllama"), DATA_PATH / "empty"),
        (Input(model="tinyllama", image="testimage"), DATA_PATH / "basic"),
        (Input(model="tinyllama", image="testimage", args=Args(port="2020")), DATA_PATH / "portmapping"),
        (
            Input(
                model="longpathtoablobsha", image="testimage", args=Args(MODEL="modelfromstore"), model_file_exists=True
            ),
            DATA_PATH / "modelfromstore",
        ),
        (
            Input(
                model="longpathtoablobsha",
                image="testimage",
                args=Args(MODEL="modelfromstore_ct"),
                model_file_exists=True,
                chat_template="chat_template_file",
                chat_template_file_exists=True,
            ),
            DATA_PATH / "modelfromstore_ct",
        ),
    ],
)
def test_quadlet_generate(input: Input, expected_files_path: Path, monkeypatch):
    expected_files = dict()
    for file in os.listdir(expected_files_path):
        with open(os.path.join(expected_files_path, file)) as f:
            expected_files[file] = f.read()

    existence = {
        input.model: input.model_file_exists,
        input.chat_template: input.chat_template_file_exists,
    }

    monkeypatch.setattr("os.path.exists", lambda path: existence.get(path, False))

    monkeypatch.setattr(Quadlet, "_gen_env", lambda self, quadlet_file: None)

    for file in Quadlet(input.model, input.chat_template, input.args, input.exec_args).generate():
        assert file.filename in expected_files

        with io.StringIO() as sio:
            file._write(sio)
            sio.seek(0)  # rewind
            assert expected_files[file.filename] == sio.read()
            del expected_files[file.filename]

    assert expected_files == dict()
