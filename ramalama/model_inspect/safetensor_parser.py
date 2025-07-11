import json
import struct

import ramalama.console as console
from ramalama.model_inspect.error import ParseError
from ramalama.model_inspect.safetensor_info import SafetensorModelInfo

# Based on safetensor format description:
# https://github.com/huggingface/safetensors?tab=readme-ov-file#format


class SafetensorInfoParser:

    @staticmethod
    def is_model_safetensor(model_name: str) -> bool:

        # There is no magic number or something similar, so we only rely on the naming of the file here
        return model_name.endswith(".safetensor") or model_name.endswith(".safetensors")

    @staticmethod
    def parse(model_name: str, model_registry: str, model_path: str) -> SafetensorModelInfo:
        try:
            with open(model_path, "rb") as model_file:
                prefix = '<'
                typestring = f"{prefix}Q"

                header_size = struct.unpack(typestring, model_file.read(8))[0]
                header = json.loads(model_file.read(header_size))

                return SafetensorModelInfo(model_name, model_registry, model_path, header)

        except Exception as ex:
            msg = f"Failed to parse safetensor model '{model_path}': {ex}"
            console.warning(msg)
            raise ParseError(msg)
