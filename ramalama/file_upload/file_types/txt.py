from ramalama.file_upload.file_types.base import BaseFileUpload


class TXTFileUpload(BaseFileUpload):
    def load(self) -> str:
        """
        Load the content of the text file.
        """

        # TODO: Support for non-default encodings?
        with open(self.file, 'r') as f:
            return f.read()
