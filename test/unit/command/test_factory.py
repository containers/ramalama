import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ramalama.command.context import (
    RamalamaArgsContext,
    RamalamaCommandContext,
    RamalamaHostContext,
    RamalamaModelContext,
)
from ramalama.command.error import InvalidInferenceEngineSpecError
from ramalama.command.factory import CommandFactory
from ramalama.transports.transport_factory import New


@pytest.fixture
def spec_files() -> dict[str, Path]:
    spec_dir = Path(__file__).parent / "data" / "engines"
    files = {}
    for file in os.listdir(spec_dir):
        p = Path(spec_dir, file)
        if p.is_file():
            files[p.stem] = p
    return files


@pytest.fixture
def schema_files() -> dict[str, Path]:
    schema_dir = Path(__file__).parent / "data" / "schema"
    files = {}
    for file in os.listdir(schema_dir):
        p = Path(schema_dir, file)
        if p.is_file():
            version = p.name.replace("schema.", "").replace(".json", "")
            files[version] = p
    return files


@dataclass
class CLIArgs:
    runtime: str = "llama.cpp"
    subcommand: str = "serve"
    MODEL: str = "smollm:135m"
    container: bool = True
    generate: bool = False
    dry_run: bool = False
    engine: str = "podman"
    store: str = "/tmp/not-existing"
    host: str = "192.168.178.1"
    port: int = 1337
    thinking: bool = False
    context: int = 512
    temp: int = 11
    debug: bool = True
    webui: bool = True
    ngl: int = 44
    threads: int = 8
    logfile: str = "/var/tmp/ramalama.log"
    model_draft: str = "draft"
    seed: int = 12345
    runtime_args: str = "--another-arg 44 --more-args"
    cache_reuse: int = 1024
    has_mmproj: bool = True
    has_chat_template: bool = True
    max_tokens: int = 0


@dataclass
class FactoryInput:
    cli_args: CLIArgs = field(default_factory=CLIArgs)
    has_mmproj: bool = False
    has_chat_template: bool = True


@pytest.mark.parametrize(
    "input,expected_cmd",
    [
        (
            FactoryInput(),
            "llama-server --host 0.0.0.0 --port 1337 --log-file /var/tmp/ramalama.log --model /path/to/model --chat-template-file /path/to/chat-template --jinja --no-warmup --reasoning-budget 0 --alias library/smollm --ctx-size 512 --temp 11 --cache-reuse 1024 -v -ngl 44 --model-draft /path/to/draft-model -ngld 44 --threads 8 --seed 12345 --log-colors on --another-arg 44 --more-args",  # noqa: E501
        ),
        (
            FactoryInput(has_mmproj=True),
            "llama-server --host 0.0.0.0 --port 1337 --log-file /var/tmp/ramalama.log --model /path/to/model --mmproj /path/to/mmproj --no-jinja --no-warmup --reasoning-budget 0 --alias library/smollm --ctx-size 512 --temp 11 --cache-reuse 1024 -v -ngl 44 --model-draft /path/to/draft-model -ngld 44 --threads 8 --seed 12345 --log-colors on --another-arg 44 --more-args",  # noqa: E501
        ),
        (
            FactoryInput(has_chat_template=False),
            "llama-server --host 0.0.0.0 --port 1337 --log-file /var/tmp/ramalama.log --model /path/to/model --jinja --no-warmup --reasoning-budget 0 --alias library/smollm --ctx-size 512 --temp 11 --cache-reuse 1024 -v -ngl 44 --model-draft /path/to/draft-model -ngld 44 --threads 8 --seed 12345 --log-colors on --another-arg 44 --more-args",  # noqa: E501
        ),
        (
            FactoryInput(cli_args=CLIArgs(runtime_args="")),
            "llama-server --host 0.0.0.0 --port 1337 --log-file /var/tmp/ramalama.log --model /path/to/model --chat-template-file /path/to/chat-template --jinja --no-warmup --reasoning-budget 0 --alias library/smollm --ctx-size 512 --temp 11 --cache-reuse 1024 -v -ngl 44 --model-draft /path/to/draft-model -ngld 44 --threads 8 --seed 12345 --log-colors on",  # noqa: E501
        ),
        (
            FactoryInput(cli_args=CLIArgs(max_tokens=99, runtime_args="")),
            "llama-server --host 0.0.0.0 --port 1337 --log-file /var/tmp/ramalama.log --model /path/to/model --chat-template-file /path/to/chat-template --jinja --no-warmup --reasoning-budget 0 --alias library/smollm --ctx-size 512 --temp 11 --cache-reuse 1024 -v -ngl 44 --model-draft /path/to/draft-model -ngld 44 --threads 8 --seed 12345 --log-colors on -n 99",  # noqa: E501
        ),
    ],
)
def test_command_factory(
    input: FactoryInput,
    expected_cmd: str,
    spec_files: dict[str, Path],
    schema_files: dict[str, Path],
):
    cli_args = input.cli_args.__dict__

    model = New(cli_args["MODEL"], argparse.Namespace(**cli_args))
    mock_model = MagicMock()
    mock_model.model_name = model.model_name
    mock_model.model_tag = model.model_tag
    mock_model.model_organization = model.model_organization
    mock_model.model_alias = f"{model.model_organization}/{model.model_name}"

    mock_model._get_entry_model_path.return_value = "/path/to/model"
    mock_model._get_mmproj_path.return_value = "/path/to/mmproj" if input.has_mmproj else ""
    mock_model._get_chat_template_path.return_value = "/path/to/chat-template" if input.has_chat_template else ""

    mock_draft_model = MagicMock()
    mock_draft_model._get_entry_model_path.return_value = "/path/to/draft-model"
    mock_model.draft_model = mock_draft_model

    model_ctx = RamalamaModelContext(
        model=mock_model,
        is_container=cli_args["container"],
        should_generate=cli_args["generate"],
        dry_run=cli_args["dry_run"],
    )
    func_ctx = RamalamaHostContext(cli_args["container"], True, True, True, None)
    arg_ctx = RamalamaArgsContext.from_argparse(argparse.Namespace(**cli_args))
    ctx = RamalamaCommandContext(arg_ctx, model_ctx, func_ctx)

    factory = CommandFactory(spec_files, schema_files)
    cmd = factory.create(cli_args["runtime"], cli_args["subcommand"], ctx)

    print(" ".join(cmd))
    assert " ".join(cmd) == expected_cmd


def test_command_factory_missing_spec(spec_files: dict[str, Path], schema_files: dict[str, Path]):
    factory = CommandFactory(spec_files, schema_files)
    runtime = "non-existing-runtime"
    with pytest.raises(FileNotFoundError) as ex:
        factory.create(runtime, "run", None)
    assert ex.match(f"No specification file found for runtime '{runtime}' ")


def test_command_factory_spec_missing_version(spec_files: dict[str, Path], schema_files: dict[str, Path]):
    factory = CommandFactory(spec_files, schema_files)
    runtime = "llama.cpp.missing.version"
    with pytest.raises(InvalidInferenceEngineSpecError) as ex:
        factory.create(runtime, "run", None)
    assert ex.match("Missing required field 'schema_version'")


def test_command_factory_spec_invalid(spec_files: dict[str, Path], schema_files: dict[str, Path]):
    factory = CommandFactory(spec_files, schema_files)
    runtime = "llama.cpp.invalid"
    with pytest.raises(InvalidInferenceEngineSpecError) as ex:
        factory.create(runtime, "run", None)
    assert ex.match("'binary' is a required property.*")


def test_command_factory_spec_unknown_operation(spec_files: dict[str, Path], schema_files: dict[str, Path]):
    factory = CommandFactory(spec_files, schema_files)
    runtime = "llama.cpp"
    with pytest.raises(NotImplementedError) as ex:
        factory.create(runtime, "execute", None)
    assert ex.match("The specification for 'llama.cpp' does not implement command 'execute' ")


def test_command_factory_missing_schema(spec_files: dict[str, Path]):
    factory = CommandFactory(spec_files, {})
    with pytest.raises(FileNotFoundError) as ex:
        factory.create("llama.cpp", "run", None)
    assert ex.match("No schema file found for spec version '1.0.0' ")
