"""ramalama compat module."""

# Python 3.10 doesn't have StrEnum
try:
    from enum import StrEnum
except ImportError:
    from enum import Enum

    class StrEnum(str, Enum):  # type: ignore[no-redef]
        """StrEnum class for Python 3.10."""

        def __str__(self):
            return self.value