import base64
import mimetypes

from ramalama.file_loaders.file_types.base import BaseFileLoader


class BasicImageFileLoader(BaseFileLoader):
    @staticmethod
    def file_extensions() -> set[str]:
        return {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".tiff",
            ".tif",
            ".webp",
            ".ico",
        }

    @staticmethod
    def load(file: str) -> str:
        """
        Load the content of the text file.
        """

        mime_type, _ = mimetypes.guess_type(file)
        with open(file, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")

        return f"data:{mime_type};base64,{data}"
