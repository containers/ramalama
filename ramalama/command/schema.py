from typing import Optional

VERSION_FIELD = "schema_version"


class CommandSpecV1:

    class Option:
        name: str
        description: Optional[str]
        value: Optional[str]
        required: bool
        condition: Optional[str]

        @staticmethod
        def from_dict(d: dict) -> "CommandSpecV1.Option":
            option = CommandSpecV1.Option()
            option.name = d["name"]
            option.description = d.get("description", None)
            option.value = d.get("value", None)
            option.required = d.get("required", True)
            option.condition = d.get("if", None)

            return option

    class Engine:
        name: str
        binary: str
        options: list["CommandSpecV1.Option"]

        @staticmethod
        def from_dict(d: dict) -> "CommandSpecV1.Engine":
            engine = CommandSpecV1.Engine()

            engine.name = d["name"]
            engine.binary = d["binary"]
            engine.options = []
            for option in d["options"]:
                opt = CommandSpecV1.Option.from_dict(option)
                engine.options.append(opt)

            return engine

    class Command:
        name: str
        engine: "CommandSpecV1.Engine"

        @staticmethod
        def from_dict(d: dict) -> "CommandSpecV1.Command":
            command = CommandSpecV1.Command()
            command.name = d["name"]
            command.engine = CommandSpecV1.Engine.from_dict(d["inference_engine"])
            return command

    def __init__(self, command: "CommandSpecV1.Command"):
        self.command = command

    @staticmethod
    def from_dict(d: dict, command: str) -> Optional["CommandSpecV1"]:
        for cmd in d.get("commands", []):
            if cmd["name"] == command:
                return CommandSpecV1(CommandSpecV1.Command.from_dict(cmd))

        return None
