import argparse
import ast
import json
from pathlib import Path
from typing import Any

import jinja2
import jsonschema
import yaml

from ramalama.command import context, error, schema
from ramalama.config import get_inference_schema_files, get_inference_spec_files


def is_truthy(resolved_stmt: str) -> bool:
    return resolved_stmt not in ["None", "False", "", "[]", "{}"]


class CommandFactory:

    def __init__(self, spec_files: dict[str, Path], schema_files: dict[str, Path]):
        self.spec_files = spec_files
        self.schema_files = schema_files

    def create(self, runtime: str, command: str, ctx: context.RamalamaCommandContext) -> list[str]:
        spec_file = self.spec_files.get(runtime, None)
        if spec_file is None:
            raise FileNotFoundError(f"No specification file found for runtime '{runtime}' ")
        spec_data = CommandFactory.load_file(spec_file)
        if schema.VERSION_FIELD not in spec_data:
            raise error.InvalidInferenceEngineSpecError(
                str(spec_file), f"Missing required field '{schema.VERSION_FIELD}' "
            )

        schema_file = self.schema_files.get(spec_data[schema.VERSION_FIELD].replace(".", "-"), None)
        if schema_file is None:
            raise FileNotFoundError(f"No schema file found for spec version '{spec_data[schema.VERSION_FIELD]}' ")

        schema_data = CommandFactory.load_file(schema_file)

        try:
            CommandFactory.validate_spec(spec_data, schema_data)
        except Exception as ex:
            raise error.InvalidInferenceEngineSpecError(str(spec_file), str(ex)) from ex

        spec = schema.CommandSpecV1.from_dict(spec_data, command)
        if spec is None:
            raise NotImplementedError(f"The specification for '{runtime}' does not implement command '{command}' ")

        return CommandFactory.resolve_cmd(spec, ctx)

    @staticmethod
    def resolve_cmd(spec: schema.CommandSpecV1, ctx: context.RamalamaCommandContext) -> list[str]:
        engine = spec.command.engine

        cmd = [engine.binary]
        for option in engine.options:
            should_add = option.condition is None or is_truthy(CommandFactory.eval_stmt(option.condition, ctx))
            if not should_add:
                continue

            if option.value is None:
                cmd.append(option.name)
                continue

            value = CommandFactory.eval_stmt(option.value, ctx)
            if is_truthy(value):
                if option.name:
                    cmd.append(option.name)

                if value.startswith("[") and value.endswith("]"):
                    cmd.extend(str(v) for v in ast.literal_eval(value))
                else:
                    cmd.append(str(value))

        return cmd

    @staticmethod
    def eval_stmt(stmt: str, ctx: context.RamalamaCommandContext) -> Any:
        if not ("{{" in stmt and "}}" in stmt):
            return stmt

        return jinja2.Template(stmt).render(
            {
                "args": ctx.args,
                "model": ctx.model,
                "host": ctx.host,
            }
        )

    @staticmethod
    def validate_spec(spec_data: dict, schema: dict):
        jsonschema.validate(instance=spec_data, schema=schema)

    @staticmethod
    def load_file(path: Path) -> dict:
        if not path.exists():
            raise FileNotFoundError(f"File '{path}' not found")

        with open(path, "r") as f:
            if path.suffix == ".json":
                return json.load(f)
            elif path.suffix in [".yaml", ".yml"]:
                return yaml.safe_load(f)

            raise NotImplementedError(f"File extension '{path.suffix}' not supported")


def assemble_command(cli_args: argparse.Namespace) -> list[str]:
    cmd_factory = CommandFactory(get_inference_spec_files(), get_inference_schema_files())
    runtime = str(cli_args.runtime)
    command = str(cli_args.subcommand)
    ctx = context.RamalamaCommandContext.from_argparse(cli_args)
    return cmd_factory.create(runtime, command, ctx)
