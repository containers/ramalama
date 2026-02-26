"""ramalama compat module."""

import os
import sys
from contextlib import contextmanager
from tempfile import NamedTemporaryFile as _NamedTemporaryFile

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):  # type: ignore[no-redef]
        """StrEnum class for Python 3.10."""

        def __str__(self) -> str:
            return self.value


if sys.version_info >= (3, 12):
    NamedTemporaryFile = _NamedTemporaryFile
else:
    # Python 3.10 doesn't have NamedTemporaryFile delete_on_close
    @contextmanager
    def NamedTemporaryFile(
        mode: str = "w+b",
        buffering: int = -1,
        encoding: str | None = None,
        newline: str | None = None,
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | os.PathLike[str] | None = None,
        delete: bool = True,
        *,
        errors: str | None = None,
        delete_on_close: bool = True,
    ):
        f = _NamedTemporaryFile(
            mode=mode,
            buffering=buffering,
            encoding=encoding,
            newline=newline,
            suffix=suffix,
            prefix=prefix,
            dir=dir,
            delete=delete and delete_on_close,
            errors=errors,
        )
        try:
            yield f
        finally:
            if delete:
                if not f.closed:
                    f.close()
                if os.path.exists(f.name):
                    os.unlink(f.name)
