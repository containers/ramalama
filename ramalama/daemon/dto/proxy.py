import json
from dataclasses import dataclass


@dataclass
class RunningModelResponse:

    id: str
    name: str
    organization: str
    tag: str
    cmd: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "organization": self.organization,
            "tag": self.tag,
            "cmd": self.cmd,
        }

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), indent=4, sort_keys=True)


def running_model_list_to_dict(models: list[RunningModelResponse]) -> list[dict]:
    return [model.to_dict() for model in models]


def running_model_list_serialize(models: list[RunningModelResponse]) -> str:
    return json.dumps(running_model_list_to_dict(models), indent=4, sort_keys=True)
