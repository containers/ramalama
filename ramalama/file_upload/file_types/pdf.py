from ramalama.file_upload.file_types.base import BaseFileUpload


class PDFFileUpload(BaseFileUpload):
    def load(self) -> str:
        """
        Load the content of the PDF file.
        This method should be implemented to handle PDF file reading.
        """
        return ""
