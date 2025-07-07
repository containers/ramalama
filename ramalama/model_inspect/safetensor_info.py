import json
from typing import Any, Dict

from ramalama.model_inspect.base_info import ModelInfoBase, adjust_new_line


class SafetensorModelInfo(ModelInfoBase):

    def __init__(
        self,
        Name: str,
        Registry: str,
        Path: str,
        header_data: Dict[str, Any],
    ):
        super().__init__(Name, Registry, Path)

        self.Header: Dict[str, Any] = header_data

    def serialize(self, json: bool = False, all: bool = False) -> str:
        if json:
            return self.to_json(all)

        fmt = ""
        metadata = self.Header.get("__metadata__", {})
        if isinstance(metadata, dict):
            fmt = metadata.get("format", "")

        ret = super().serialize()
        ret = ret + adjust_new_line(f"   Format: {fmt}")
        metadata_header = "   Header: "
        if not all:
            metadata_header = metadata_header + f"{len(self.Header)} entries"
        ret = ret + adjust_new_line(metadata_header)
        if all:
            for key, value in sorted(self.Header.items()):
                ret = ret + adjust_new_line(f"      {key}: {value}")

        return ret

    def to_json(self, all: bool = False) -> str:
        if all:
            return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

        d = {k: v for k, v in self.__dict__.items() if k != "Header"}
        d["Metadata"] = len(self.Header)
        return json.dumps(d, sort_keys=True, indent=4)
