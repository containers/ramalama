import os
from string import Template
from warnings import warn

from ramalama.file_upload.file_types import base, txt

SUPPORTED_EXTENSIONS = {
    '.txt': txt.TXTFileUpload,
    '.sh': txt.TXTFileUpload,
    '.md': txt.TXTFileUpload,
    '.yaml': txt.TXTFileUpload,
    '.yml': txt.TXTFileUpload,
    '.json': txt.TXTFileUpload,
    '.csv': txt.TXTFileUpload,
    '.toml': txt.TXTFileUpload,
}


class BaseFileUploader:
    """
    Base class for file upload handlers.
    This class should be extended by specific file type handlers.
    """

    def __init__(self, files: list[base.BaseFileUpload], delim_string: str = "<!--start_document $name-->"):
        self.files = files
        self.document_delimiter: Template = Template(delim_string)

    def load(self) -> str:
        """
        Generate the output string by concatenating the processed files.
        """
        output = (f"\n{self.document_delimiter.substitute(name=f.file)}\n{f.load()}" for f in self.files)
        return "".join(output)


class FileUpLoader(BaseFileUploader):
    def __init__(self, file_path: str):
        if not os.path.exists(file_path):
            raise ValueError(f"{file_path} does not exist.")

        if not os.path.isdir(file_path):
            files = [file_path]
        else:
            files = [os.path.join(root, name) for root, _, files in os.walk(file_path) for name in files]

        extensions = [os.path.splitext(f)[1].lower() for f in files]

        if set(extensions) - set(SUPPORTED_EXTENSIONS):
            warning_message = (
                f"Unsupported file types found: {set(extensions) - set(SUPPORTED_EXTENSIONS)}\n"
                f"Supported types are: {set(SUPPORTED_EXTENSIONS.keys())}"
            )
            warn(warning_message)

        files = [SUPPORTED_EXTENSIONS[ext](file=f) for ext, f in zip(extensions, files) if ext in SUPPORTED_EXTENSIONS]
        super().__init__(files=files)
