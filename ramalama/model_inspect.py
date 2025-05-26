import json
import shutil
import sys
from dataclasses import dataclass
from typing import Any, Dict

from ramalama.endian import GGUFEndian


def get_terminal_width():
    if sys.stdout.isatty():
        return shutil.get_terminal_size().columns
    return 80


def adjust_new_line(line: str) -> str:
    filler = "..."
    max_width = get_terminal_width()
    adjusted_length = max_width - len(filler)

    adjust_for_newline = 1 if line.endswith("\n") else 0
    if len(line) - adjust_for_newline > max_width:
        return line[: adjusted_length - adjust_for_newline] + filler + "\n" if adjust_for_newline == 1 else ""
    if not line.endswith("\n"):
        return line + "\n"
    return line


@dataclass
class Tensor:
    name: str
    n_dimensions: int
    dimensions: list[int]
    type: str
    offset: int


@dataclass
class ModelInfoBase:
    Name: str
    Registry: str
    Path: str

    def serialize(self, json: bool = False) -> str:
        ret = adjust_new_line(f"{self.Name}\n")
        ret = ret + adjust_new_line(f"   Path: {self.Path}\n")
        ret = ret + adjust_new_line(f"   Registry: {self.Registry}")
        return ret

    def to_json(self) -> str:
        return json.dumps(self, sort_keys=True, indent=4)


class GGUFModelInfo(ModelInfoBase):
    MAGIC_NUMBER = "GGUF"
    VERSION = 3

    def __init__(
        self,
        Name: str,
        Registry: str,
        Path: str,
        metadata: Dict[str, Any],
        tensors: list[Tensor],
        endianness: GGUFEndian,
    ):
        super().__init__(Name, Registry, Path)

        self.Format = GGUFModelInfo.MAGIC_NUMBER
        self.Version = GGUFModelInfo.VERSION
        self.Metadata: Dict[str, Any] = metadata
        self.Tensors: list[Tensor] = tensors
        self.Endianness: GGUFEndian = endianness

    def get_chat_template(self) -> str:
        return self.Metadata.get("chat_template", "")

    def serialize(self, json: bool = False, all: bool = False) -> str:
        if json:
            return self.to_json(all)

        ret = super().serialize()
        ret = ret + adjust_new_line(f"   Format: {GGUFModelInfo.MAGIC_NUMBER}")
        ret = ret + adjust_new_line(f"   Version: {GGUFModelInfo.VERSION}")
        ret = ret + adjust_new_line(f"   Endianness: {'little' if self.Endianness == GGUFEndian.LITTLE else 'big'}")
        metadata_header = "   Metadata: "
        if not all:
            metadata_header = metadata_header + f"{len(self.Metadata)} entries"
        ret = ret + adjust_new_line(metadata_header)
        if all:
            for key, value in sorted(self.Metadata.items()):
                ret = ret + adjust_new_line(f"      {key}: {value}")
        tensor_header = "   Tensors: "
        if not all:
            tensor_header = tensor_header + f"{len(self.Tensors)} entries"
        ret = ret + adjust_new_line(tensor_header)
        if all:
            i = 0
            for tensor in self.Tensors:
                ret = ret + adjust_new_line(
                    f"      {i}: {tensor.name, tensor.type.name, tensor.n_dimensions, tensor.offset}"
                )
                i = i + 1

        return ret

    def to_json(self, all: bool = False) -> str:
        if all:
            return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

        d = {k: v for k, v in self.__dict__.items() if k != "Metadata" and k != "Tensors"}
        d["Metadata"] = len(self.Metadata)
        d["Tensors"] = len(self.Tensors)
        return json.dumps(d, sort_keys=True, indent=4)
