import json
from dataclasses import dataclass


@dataclass
class ModelDetailsResponse:
    format: str
    family: str
    parameter_size: str
    quantization_level: str
    families: list[str]

    def to_dict(self) -> dict:
        return {
            "format": self.format,
            "family": self.family,
            "families": self.families or [],
            "parameter_size": self.parameter_size,
            "quantization_level": self.quantization_level,
        }

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), indent=4, sort_keys=True)


@dataclass
class ModelResponse:

    name: str
    modified_at: str
    size: int
    digest: str
    details: ModelDetailsResponse

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "modified_at": self.modified_at,
            "size": self.size,
            "digest": self.digest,
            "details": self.details.to_dict(),
        }

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), indent=4, sort_keys=True)


def model_list_to_dict(models: list[ModelResponse]) -> list[dict]:
    return [model.to_dict() for model in models]


def model_list_serialize(models: list[ModelResponse]) -> str:
    return json.dumps(model_list_to_dict(models), indent=4, sort_keys=True)
