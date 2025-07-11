import json
from typing import Any, Dict

from ramalama.endian import GGUFEndian
from ramalama.model_inspect.base_info import ModelInfoBase, Tensor, adjust_new_line


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
