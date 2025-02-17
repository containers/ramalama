import io
import struct
from enum import IntEnum
from typing import Any, Dict

import ramalama.console as console
from ramalama.model_inspect import GGUFModelInfo, Tensor


# Based on ggml_type in
# https://github.com/ggml-org/ggml/blob/master/docs/gguf.md#file-structure
class GGML_TYPE(IntEnum):
    GGML_TYPE_F32 = (0,)
    GGML_TYPE_F16 = (1,)
    GGML_TYPE_Q4_0 = (2,)
    GGML_TYPE_Q4_1 = (3,)
    # GGML_TYPE_Q4_2 = 4, support has been removed
    # GGML_TYPE_Q4_3 = 5, support has been removed
    GGML_TYPE_Q5_0 = (6,)
    GGML_TYPE_Q5_1 = (7,)
    GGML_TYPE_Q8_0 = (8,)
    GGML_TYPE_Q8_1 = (9,)
    GGML_TYPE_Q2_K = (10,)
    GGML_TYPE_Q3_K = (11,)
    GGML_TYPE_Q4_K = (12,)
    GGML_TYPE_Q5_K = (13,)
    GGML_TYPE_Q6_K = (14,)
    GGML_TYPE_Q8_K = (15,)
    GGML_TYPE_IQ2_XXS = (16,)
    GGML_TYPE_IQ2_XS = (17,)
    GGML_TYPE_IQ3_XXS = (18,)
    GGML_TYPE_IQ1_S = (19,)
    GGML_TYPE_IQ4_NL = (20,)
    GGML_TYPE_IQ3_S = (21,)
    GGML_TYPE_IQ2_S = (22,)
    GGML_TYPE_IQ4_XS = (23,)
    GGML_TYPE_I8 = (24,)
    GGML_TYPE_I16 = (25,)
    GGML_TYPE_I32 = (26,)
    GGML_TYPE_I64 = (27,)
    GGML_TYPE_F64 = (28,)
    GGML_TYPE_IQ1_M = (29,)


# Based on gguf_metadata_value_type in
# https://github.com/ggml-org/ggml/blob/master/docs/gguf.md#file-structure
class GGUFValueType(IntEnum):
    UINT8 = (0,)  # 8-bit unsigned integer
    INT8 = (1,)  # 8-bit signed integer
    UINT16 = (2,)  # 16-bit unsigned little-endian integer
    INT16 = (3,)  # 16-bit signed little-endian integer
    UINT32 = (4,)  # 32-bit unsigned little-endian integer
    INT32 = (5,)  # 32-bit signed little-endian integer
    FLOAT32 = (6,)  # 32-bit IEEE754 floating point number

    # boolean of 1-byte value where 0 is false and 1 is true.
    # Anything else is invalid, and should be treated as either the model being invalid or the reader being buggy.
    BOOL = (7,)

    STRING = (8,)  # UTF-8 non-null-terminated string, with length prepended.

    # Array of other values, with the length and type prepended.
    # Arrays can be nested, and the length of the array is the number of elements in the array, not the number of bytes.
    ARRAY = (9,)

    UINT64 = (10,)  # 64-bit unsigned little-endian integer
    INT64 = (11,)  # 64-bit signed little-endian integer
    FLOAT64 = (12,)  # 64-bit IEEE754 floating point number


# Mapping GGUFs value types to python struct librarys format characters
# see https://docs.python.org/3/library/struct.html#format-characters
GGUF_VALUE_TYPE_FORMAT: Dict[GGUFValueType, str] = {
    GGUFValueType.UINT8: "B",
    GGUFValueType.INT8: "b",
    GGUFValueType.UINT16: "H",
    GGUFValueType.INT16: "h",
    GGUFValueType.UINT32: "I",
    GGUFValueType.INT32: "i",
    GGUFValueType.FLOAT32: "f",
    GGUFValueType.BOOL: "?",
    GGUFValueType.UINT64: "Q",
    GGUFValueType.INT64: "q",
    GGUFValueType.FLOAT64: "d",
}

GGUF_NUMBER_FORMATS: list[GGUFValueType] = [
    GGUFValueType.UINT8,
    GGUFValueType.INT8,
    GGUFValueType.UINT16,
    GGUFValueType.INT16,
    GGUFValueType.UINT32,
    GGUFValueType.INT32,
    GGUFValueType.FLOAT32,
    GGUFValueType.UINT64,
    GGUFValueType.INT64,
    GGUFValueType.FLOAT64,
]


class ParseError(Exception):
    pass


class GGUFInfoParser:

    def is_model_gguf(model_path: str) -> bool:
        try:
            with open(model_path, "rb") as model_file:
                magic_number = GGUFInfoParser.read_string(model_file, 4)
                return magic_number == GGUFModelInfo.MAGIC_NUMBER
        except Exception as ex:
            console.warning(f" Failed to read model '{model_path}': {ex}")
            return False

    @staticmethod
    def read_string(model: io.BufferedReader, length: int = -1) -> str:
        if length == -1:
            type_string = GGUF_VALUE_TYPE_FORMAT[GGUFValueType.UINT64]
            length = struct.unpack(type_string, model.read(struct.calcsize(type_string)))[0]
        return model.read(length).decode("utf-8")

    @staticmethod
    def read_number(model: io.BufferedReader, value_type: GGUFValueType, model_uses_little_endian: bool) -> float:
        if value_type not in GGUF_NUMBER_FORMATS:
            raise ParseError(f"Value type '{value_type}' not in format dict")
        typestring = f"{'<' if model_uses_little_endian else '>'}{GGUF_VALUE_TYPE_FORMAT[value_type]}"
        return struct.unpack(typestring, model.read(struct.calcsize(typestring)))[0]

    @staticmethod
    def read_bool(model: io.BufferedReader, model_uses_little_endian: bool) -> bool:
        typestring = f"{'<' if model_uses_little_endian else '>'}{GGUF_VALUE_TYPE_FORMAT[GGUFValueType.BOOL]}"
        value = struct.unpack(typestring, model.read(struct.calcsize(typestring)))[0]
        if value not in [0, 1]:
            raise ParseError(f"Invalid bool value '{value}'")
        return value == 1

    @staticmethod
    def read_value_type(model: io.BufferedReader, model_uses_little_endian: bool) -> GGUFValueType:
        value_type = GGUFInfoParser.read_number(model, GGUFValueType.UINT32, model_uses_little_endian)
        return GGUFValueType(value_type)

    @staticmethod
    def read_value(model: io.BufferedReader, value_type: GGUFValueType, model_uses_little_endian: bool) -> Any:
        value = None
        if value_type in GGUF_NUMBER_FORMATS:
            value = GGUFInfoParser.read_number(model, value_type, model_uses_little_endian)
        elif value_type == GGUFValueType.BOOL:
            value = GGUFInfoParser.read_bool(model, model_uses_little_endian)
        elif value_type == GGUFValueType.STRING:
            value = GGUFInfoParser.read_string(model)
        elif value_type == GGUFValueType.ARRAY:
            array_type = GGUFInfoParser.read_value_type(model, model_uses_little_endian)
            array_length = GGUFInfoParser.read_number(model, GGUFValueType.UINT64, model_uses_little_endian)
            value = [
                GGUFInfoParser.read_value(model, array_type, model_uses_little_endian) for _ in range(array_length)
            ]

        if value is not None:
            return value
        raise ParseError(f"Unknown type '{value_type}'")

    def parse(model_name: str, model_registry: str, model_path: str, cli_args) -> GGUFModelInfo:
        # By default, models are little-endian encoded
        is_little_endian = True

        with open(model_path, "rb") as model:
            magic_number = GGUFInfoParser.read_string(model, 4)
            if magic_number != GGUFModelInfo.MAGIC_NUMBER:
                raise ParseError(f"Invalid GGUF magic number '{magic_number}'")

            gguf_version = GGUFInfoParser.read_number(model, GGUFValueType.UINT32, is_little_endian)
            # If the read GGUF version is different, then the model could be big-endian encoded
            if gguf_version != GGUFModelInfo.VERSION:
                is_little_endian = False
                gguf_version = GGUFInfoParser.read_number(model, GGUFValueType.UINT32, is_little_endian)
                if gguf_version != GGUFModelInfo.VERSION:
                    raise ParseError(f"Expected GGUF version '{GGUFModelInfo.VERSION}', but got '{gguf_version}'")

            tensor_count = GGUFInfoParser.read_number(model, GGUFValueType.UINT64, is_little_endian)
            metadata_kv_count = GGUFInfoParser.read_number(model, GGUFValueType.UINT64, is_little_endian)

            metadata = {}
            for _ in range(metadata_kv_count):
                key = GGUFInfoParser.read_string(model)
                value_type = GGUFInfoParser.read_value_type(model, is_little_endian)
                metadata[key] = GGUFInfoParser.read_value(model, value_type, is_little_endian)

            tensors: list[Tensor] = []
            for _ in range(tensor_count):
                name = GGUFInfoParser.read_string(model)
                n_dimensions = GGUFInfoParser.read_number(model, GGUFValueType.UINT32, is_little_endian)
                dimensions: list[int] = []
                for _ in range(n_dimensions):
                    dimensions.append(GGUFInfoParser.read_number(model, GGUFValueType.UINT64, is_little_endian))
                tensor_type = GGML_TYPE(GGUFInfoParser.read_number(model, GGUFValueType.UINT32, is_little_endian))
                offset = GGUFInfoParser.read_number(model, GGUFValueType.UINT64, is_little_endian)
                tensors.append(Tensor(name, n_dimensions, dimensions, tensor_type, offset))

            return GGUFModelInfo(model_name, model_registry, model_path, metadata, tensors, is_little_endian)
