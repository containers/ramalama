from ramalama.file_loaders.file_types.base import BaseFileLoader


class PDFFileLoader(BaseFileLoader):
    @staticmethod
    def file_extensions() -> set[str]:
        return {".pdf"}

    @staticmethod
    def load(file: str) -> str:
        """
        Load the content of the PDF file.
        This method should be implemented to handle PDF file reading.
        """
        return ""
