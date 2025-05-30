from enum import IntEnum


class GGUFEndian(IntEnum):
    LITTLE = 0
    BIG = 1

    little = LITTLE
    big = BIG

    def __str__(self):
        return self.name


class EndianMismatchError(Exception):
    pass
