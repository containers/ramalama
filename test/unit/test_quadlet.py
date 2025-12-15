import io
import os
from pathlib import Path
from typing import Optional

import pytest

from ramalama.quadlet import Quadlet


class Args:
    def __init__(
        self,
        name: str = "",
        rag: str = "",
        port: str = "",
        host: str = "0.0.0.0",
        env: list = [],
        MODEL: Optional[str] = None,
        add_to_unit=None,
    ):
        self.name = name
        self.rag = rag
        self.env = env
        self.port = port
        self.host = host
        self.image = "testimage"
        if MODEL is not None:
            self.MODEL = MODEL
        self.add_to_unit = add_to_unit


class Input:
    def __init__(
        self,
        model_name: str = "",
        model_src_blob: str = "",
        model_dest_name: str = "",
        model_file_exists: bool = False,
        chat_template_src_blob: str = "",
        chat_template_dest_name: str = "",
        chat_template_file_exists: bool = False,
        mmproj_src_blob: str = "",
        mmproj_dest_name: str = "",
        mmproj_file_exists: bool = False,
        image: str = "",
        args: Args = Args(),
        exec_args: list = [],
        accel_type: str = "cuda",
        artifact: str = "",
        model_parts: Optional[list] = None,
    ):
        self.model_name = model_name
        self.model_src_blob = model_src_blob
        self.model_dest_name = model_dest_name
        self.model_file_exists = model_file_exists
        self.chat_template_src_blob = chat_template_src_blob
        self.chat_template_dest_name = chat_template_dest_name
        self.chat_template_file_exists = chat_template_file_exists
        self.mmproj_src_blob = mmproj_src_blob
        self.mmproj_dest_name = mmproj_dest_name
        self.mmproj_file_exists = mmproj_file_exists
        self.image = image
        self.args = args
        self.exec_args = exec_args
        self.accel_type = accel_type
        self.artifact = artifact
        self.model_parts = model_parts


DATA_PATH = Path(__file__).parent / "data" / "test_quadlet"


@pytest.mark.parametrize(
    "input,expected_files_path",
    [
        (
            Input(
                model_name="tinyllama",
                model_src_blob="sha256-2af3b81862c6be03c769683af18efdadb2c33f60ff32ab6f83e42c043d6c7816",
                model_dest_name="/mnt/models/tinyllama",
            ),
            DATA_PATH / "empty",
        ),
        (
            Input(
                model_name="tinyllama",
                model_src_blob="sha256-2af3b81862c6be03c769683af18efdadb2c33f60ff32ab6f83e42c043d6c7816",
                model_dest_name="/mnt/models/tinyllama",
                image="testimage",
            ),
            DATA_PATH / "basic",
        ),
        (
            Input(
                model_name="tinyllama",
                model_src_blob="sha256-2af3b81862c6be03c769683af18efdadb2c33f60ff32ab6f83e42c043d6c7816",
                model_dest_name="/mnt/models/tinyllama",
                image="testimage",
                args=Args(port="2020"),
            ),
            DATA_PATH / "portmapping",
        ),
        (
            Input(
                model_name="tinyllama",
                model_src_blob="sha256-2af3b81862c6be03c769683af18efdadb2c33f60ff32ab6f83e42c043d6c7816",
                model_dest_name="tinyllama",
                image="testimage",
                args=Args(port="2020", host="127.0.0.1"),
                accel_type="intel",
            ),
            DATA_PATH / "localhost",
        ),
        (
            Input(
                model_name="modelfromstore",
                model_src_blob="sha256-2af3b81862c6be03c769683af18efdadb2c33f60ff32ab6f83e42c043d6c7816",
                model_dest_name="/mnt/models/modelfromstore",
                image="testimage",
                args=Args(MODEL="modelfromstore"),
                model_file_exists=True,
            ),
            DATA_PATH / "modelfromstore",
        ),
        (
            Input(
                model_name="modelfromstore_ct",
                model_src_blob="sha256-2af3b81862c6be03c769683af18efdadb2c33f60ff32ab6f83e42c043d6c7816",
                model_dest_name="/mnt/models/modelfromstore_ct",
                image="testimage",
                args=Args(MODEL="modelfromstore_ct"),
                model_file_exists=True,
                chat_template_src_blob="sha256-c21bc76d14f19f6552bfd8bbf4e5f57494169b902c73aa12ce3ce855466477fa",
                chat_template_dest_name="/mnt/models/chat_template",
                chat_template_file_exists=True,
            ),
            DATA_PATH / "modelfromstore_ct",
        ),
        (
            Input(
                model_name="modelfromstore_mmproj",
                model_src_blob="sha256-2af3b81862c6be03c769683af18efdadb2c33f60ff32ab6f83e42c043d6c7816",
                model_dest_name="/mnt/models/modelfromstore_mmproj",
                image="testimage",
                args=Args(MODEL="modelfromstore_mmproj"),
                model_file_exists=True,
                mmproj_src_blob="sha256-c21bc76d14f19f6552bfd8bbf4e5f57494169b902c73aa12ce3ce855466477fa",
                mmproj_dest_name="/mnt/models/modelfromstore_mmproj.mmproj",
                mmproj_file_exists=True,
            ),
            DATA_PATH / "modelfromstore_mmproj",
        ),
        (
            Input(
                model_name="modelfromstore_add_to_unit",
                model_src_blob="sha256-2af3b81862c6be03c769683af18efdadb2c33f60ff32ab6f83e42c043d6c7816",
                model_dest_name="longpathtoablobsha",
                image="testimage",
                args=Args(
                    MODEL="modelfromstore_add_to_unit",
                    add_to_unit=[
                        "section1:key0:value0",
                        "section1:key1:valu:e:1",
                        "section1:key2:value1:",
                        "Container:test:dummy",
                    ],
                ),
                model_file_exists=True,
                mmproj_src_blob="sha256-c21bc76d14f19f6552bfd8bbf4e5f57494169b902c73aa12ce3ce855466477fa",
                mmproj_dest_name="model.mmproj",
                mmproj_file_exists=True,
            ),
            DATA_PATH / "modelfromstore_add_to_unit",
        ),
        (
            Input(
                model_name="oci-model",
                model_src_blob="oci://registry.example.com/model:latest",
                model_dest_name="/mnt/models/model.file",
                image="testimage",
                model_file_exists=False,
            ),
            DATA_PATH / "oci_basic",
        ),
        (
            Input(
                model_name="oci-model-port",
                model_src_blob="oci://registry.example.com/model:latest",
                model_dest_name="/mnt/models/model.file",
                image="testimage",
                args=Args(port="8080"),
                model_file_exists=False,
            ),
            DATA_PATH / "oci_port",
        ),
        (
            Input(
                model_name="oci-model-rag",
                model_src_blob="oci://registry.example.com/model:latest",
                model_dest_name="/mnt/models/model.file",
                image="testimage",
                args=Args(rag="oci://registry.example.com/rag:latest"),
                model_file_exists=False,
            ),
            DATA_PATH / "oci_rag",
        ),
        (
            Input(
                model_name="gpt-oss-120b",
                model_src_blob="sha256-e2865eb6c1df7b2ffbebf305cd5d9074d5ccc0fe3b862f98d343a46dad1606f9",
                model_dest_name="/mnt/models/gpt-oss-120b-mxfp4-00001-of-00003.gguf",
                image="testimage",
                model_file_exists=True,
                model_parts=[
                    (
                        "sha256-e2865eb6c1df7b2ffbebf305cd5d9074d5ccc0fe3b862f98d343a46dad1606f9",
                        "/mnt/models/gpt-oss-120b-mxfp4-00001-of-00003.gguf",
                    ),
                    (
                        "sha256-81856b5b996da9c9fd68397d49671264ead380a8355b3c83284eae5e21e998ed",
                        "/mnt/models/gpt-oss-120b-mxfp4-00002-of-00003.gguf",
                    ),
                    (
                        "sha256-38b087fffe4b5ba5d62fa7761ed7278a07fef7a6145b9744b11205b851021dce",
                        "/mnt/models/gpt-oss-120b-mxfp4-00003-of-00003.gguf",
                    ),
                ],
            ),
            DATA_PATH / "multipart",
        ),
    ],
)
def test_quadlet_generate(input: Input, expected_files_path: Path, monkeypatch):
    expected_files = dict()
    for file in os.listdir(expected_files_path):
        with open(os.path.join(expected_files_path, file)) as f:
            expected_files[file] = f.read()

    existence = {
        input.model_src_blob: input.model_file_exists,
        input.chat_template_src_blob: input.chat_template_file_exists,
        input.mmproj_src_blob: input.mmproj_file_exists,
    }

    # Add existence checks for all model parts
    if input.model_parts:
        for src, _ in input.model_parts:
            existence[src] = input.model_file_exists

    monkeypatch.setattr("os.path.exists", lambda path: existence.get(path, False))
    monkeypatch.setattr(Quadlet, "_gen_env", lambda self, quadlet_file: None)
    monkeypatch.setattr("ramalama.quadlet.get_accel", lambda: input.accel_type)

    for file in Quadlet(
        input.model_name,
        (input.model_src_blob, input.model_dest_name),
        (input.chat_template_src_blob, input.chat_template_dest_name),
        (input.mmproj_src_blob, input.mmproj_dest_name),
        input.args,
        input.exec_args,
        input.artifact,
        input.model_parts,
    ).generate():
        assert file.filename in expected_files

        with io.StringIO() as sio:
            file._write(sio)
            sio.seek(0)  # rewind
            assert expected_files[file.filename] == sio.read()
            del expected_files[file.filename]

    assert expected_files == dict()
