import json
from dataclasses import dataclass
from typing import TypedDict


class ModelDetailsResponseDict(TypedDict):
    parent_model: str
    format: str
    family: str
    families: list[str]
    parameter_size: str
    quantization_level: str


@dataclass
class ModelDetailsResponse:
    format: str
    family: str
    parameter_size: str
    quantization_level: str
    families: list[str]

    def to_dict(self) -> ModelDetailsResponseDict:
        return {
            "parent_model": "",
            "format": self.format,
            "family": self.family,
            "families": self.families or [],
            "parameter_size": self.parameter_size,
            "quantization_level": self.quantization_level,
        }

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), indent=4, sort_keys=True)


class ModelResponseDict(TypedDict):
    name: str
    organization: str
    tag: str
    source: str
    model: str
    modified_at: str
    size: int
    is_partial: bool
    digest: str
    details: ModelDetailsResponseDict


@dataclass
class ModelResponse:
    name: str
    organization: str
    tag: str
    source: str
    model: str
    modified_at: str
    size: int
    is_partial: bool
    digest: str
    details: ModelDetailsResponse

    def to_dict(self) -> ModelResponseDict:
        return {
            "name": self.name,
            "organization": self.organization,
            "tag": self.tag,
            "source": self.source,
            "model": self.model,
            "modified_at": self.modified_at,
            "size": self.size,
            "is_partial": self.is_partial,
            "digest": self.digest,
            "details": self.details.to_dict(),
        }

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), indent=4, sort_keys=True)


class ModelResponseListDict(TypedDict):
    models: list[ModelResponseDict]


def model_list_to_dict(models: list[ModelResponse]) -> ModelResponseListDict:
    return {"models": [model.to_dict() for model in models]}


def model_list_serialize(models: list[ModelResponse]) -> str:
    return json.dumps(model_list_to_dict(models), indent=4, sort_keys=True)


class RunningModelResponseDict(TypedDict):
    id: str
    name: str
    organization: str
    tag: str
    source: str
    model: str
    expires_at: str
    size_vram: int
    digest: str
    cmd: str


@dataclass
class RunningModelResponse:
    id: str
    name: str
    organization: str
    tag: str
    source: str
    model: str
    expires_at: str
    size_vram: int
    digest: str
    cmd: str

    def to_dict(self) -> RunningModelResponseDict:
        return {
            "id": self.id,
            "name": self.name,
            "organization": self.organization,
            "tag": self.tag,
            "source": self.source,
            "model": self.model,
            "expires_at": self.expires_at,
            "size_vram": self.size_vram,
            "digest": self.digest,
            "cmd": self.cmd,
        }

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), indent=4, sort_keys=True)


class RunningModelListDict(TypedDict):
    models: list[RunningModelResponseDict]


def running_model_list_to_dict(models: list[RunningModelResponse]) -> RunningModelListDict:
    return {"models": [model.to_dict() for model in models]}


def running_model_list_serialize(models: list[RunningModelResponse]) -> str:
    return json.dumps(running_model_list_to_dict(models), indent=4, sort_keys=True)
