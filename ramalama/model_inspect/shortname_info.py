from ramalama.model_inspect.base_info import ModelInfoBase, adjust_new_line


class ShortNameInfo(ModelInfoBase):
    def __init__(self, name: str, source: str, *args, **kwargs):
        self.name = name
        self.source = source

    def serialize(self, json: bool = False) -> str:
        if json:
            return self.to_json()

        ret = adjust_new_line(f"{self.name}\n")
        ret = ret + adjust_new_line(f"   Source: {self.source}\n")
        return ret
