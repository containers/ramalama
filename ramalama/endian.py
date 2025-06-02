import sys
from enum import IntEnum


class GGUFEndian(IntEnum):
    LITTLE = 0
    BIG = 1

    def __str__(self):
        return self.name


def get_system_endianness() -> GGUFEndian:
    return GGUFEndian.LITTLE if sys.byteorder == 'little' else GGUFEndian.BIG


class EndianMismatchError(Exception):

    def __init__(self, host_endianness: GGUFEndian, model_endianness: GGUFEndian, *args):
        super().__init__(f"Endian mismatch of host ({host_endianness}) and model ({model_endianness})", *args)
