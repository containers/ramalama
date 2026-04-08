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
    def NamedTemporaryFile(*args, **kwargs):  # type: ignore[no-redef]
        if 'delete_on_close' in kwargs:
            delete_on_close = kwargs.pop('delete_on_close')
        else:
            delete_on_close = True
        if 'delete' in kwargs:
            delete = kwargs.pop('delete')
        else:
            delete = True
        f = _NamedTemporaryFile(*args, **kwargs, delete=delete and delete_on_close)  # type: ignore[call-overload]
        try:
            yield f
        finally:
            if delete:
                if not f.closed:
                    f.close()
                if os.path.exists(f.name):
                    os.unlink(f.name)
