import json
from dataclasses import dataclass

from ramalama.daemon.dto.errors import MissingArgumentError


@dataclass
class ServeRequest:

    model_name: str
    runtime: str
    exec_args: list[str]

    def to_dict(self) -> dict:
        return {
            "model_name": self.model_name,
            "runtime": self.runtime,
            "exec_args": [entry for entry in self.exec_args],
        }

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), indent=4, sort_keys=True)

    @staticmethod
    def from_string(data: str) -> "ServeRequest":
        data_dict = json.loads(data)

        model_name = data_dict.get("model_name", None)
        if not model_name:
            raise MissingArgumentError("model_name")

        runtime = data_dict.get("runtime", None)
        if not runtime:
            raise MissingArgumentError("runtime")

        exec_args = data_dict.get("exec_args", [])

        return ServeRequest(
            model_name=model_name,
            runtime=runtime,
            exec_args=exec_args,
        )


@dataclass
class ServeResponse:

    model_id: str
    serve_path: str

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "serve_path": self.serve_path,
        }

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), indent=4, sort_keys=True)


@dataclass
class StopServeRequest:

    model_name: str

    @staticmethod
    def from_string(data: str) -> "StopServeRequest":
        data_dict = json.loads(data)

        model_name = data_dict.get("model_name", None)
        if not model_name:
            raise MissingArgumentError("model_name")

        return StopServeRequest(model_name=model_name)

    def to_dict(self) -> dict:
        return {
            "model_name": self.model_name,
        }

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), indent=4, sort_keys=True)
