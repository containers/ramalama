import json
import shutil
import sys
from dataclasses import dataclass


def get_terminal_width():
    return shutil.get_terminal_size().columns if sys.stdout.isatty() else 80


def adjust_new_line(line: str) -> str:
    filler = "..."
    max_width = get_terminal_width()
    adjusted_length = max_width - len(filler)

    adjust_for_newline = 1 if line.endswith("\n") else 0
    if len(line) - adjust_for_newline > max_width:
        return line[: adjusted_length - adjust_for_newline] + filler + "\n" if adjust_for_newline == 1 else ""
    return line if line.endswith("\n") else line + "\n"


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
        if json:
            return self.to_json()

        ret = adjust_new_line(f"{self.Name}\n")
        ret = ret + adjust_new_line(f"   Path: {self.Path}\n")
        ret = ret + adjust_new_line(f"   Registry: {self.Registry}")
        return ret

    def to_json(self) -> str:
        return json.dumps(self.__dict__, sort_keys=True, indent=4)
