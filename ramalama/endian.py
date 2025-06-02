from enum import IntEnum


class GGUFEndian(IntEnum):
    LITTLE = 0
    BIG = 1

    def __str__(self):
        return self.name


class EndianMismatchError(Exception):
    pass
