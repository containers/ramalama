import os
from abc import ABC, abstractmethod
from string import Template
from typing import Type
from warnings import warn

from ramalama.file_loaders.file_types import base, image, txt


class BaseFileManager(ABC):
    """
    Base class for file upload handlers.
    This class should be extended by specific file type handlers.
    """

    def __init__(self):
        self.loaders = {ext.lower(): loader() for loader in self.get_loaders() for ext in loader.file_extensions()}

    def _get_loader(self, file: str) -> base.BaseFileLoader:
        loader = self.loaders.get(os.path.splitext(file)[1].lower(), None)
        if loader is None:
            raise ValueError(f"Unsupported file type: {os.path.splitext(file)[1]}")
        return loader

    @abstractmethod
    def load(self):
        pass

    @classmethod
    @abstractmethod
    def get_loaders(cls) -> list[Type[base.BaseFileLoader]]:
        pass


class TextFileManager(BaseFileManager):
    def __init__(self, delim_string: str = "<!--start_document $name-->"):
        self.document_delimiter: Template = Template(delim_string)
        super().__init__()

    @classmethod
    def get_loaders(cls) -> list[Type[base.BaseFileLoader]]:
        return [txt.TXTFileLoader]

    def load(self, files: list[str]) -> str:
        """
        Generate the output string by concatenating the processed files.
        """
        contents = []
        for file in files:
            loader = self._get_loader(file)
            content = f"\n{self.document_delimiter.substitute(name=file)}\n{loader.load(file)}"
            contents.append(content)

        return "".join(contents)


class ImageFileManager(BaseFileManager):
    @classmethod
    def get_loaders(cls) -> list[Type[base.BaseFileLoader]]:
        return [image.BasicImageFileLoader]

    def load(self, files: list[str]) -> list[str]:
        """
        Generate the output string by concatenating the processed image files.
        """
        return [self._get_loader(file).load(file) for file in files]


def unsupported_files_warning(unsupported_files: list[str], supported_extensions: list[str]):
    supported_extensions = sorted(supported_extensions)
    formatted_supported = ", ".join(supported_extensions)
    formatted_unsupported = "- " + "\n- ".join(unsupported_files)
    warn(
        f"""
⚠️  Unsupported file types detected!

Ramalama supports the following file types:
{formatted_supported}

The following unsupported files were found and ignored:
{formatted_unsupported}
    """.strip()
    )


class OpanAIChatAPIMessageBuilder:
    def __init__(self):
        self.text_manager = TextFileManager()
        self.image_manager = ImageFileManager()

    def partition_files(self, file_path: str) -> tuple[list[str], list[str], list[str]]:
        if not os.path.exists(file_path):
            raise ValueError(f"{file_path} does not exist.")

        if not os.path.isdir(file_path):
            files = [file_path]
        else:
            files = [os.path.join(root, name) for root, _, files in os.walk(file_path) for name in files]

        text_files = []
        image_files = []
        unsupported_files = []

        for file in files:
            file_type = os.path.splitext(file)[1].lower()  # Convert to lowercase for case-insensitive matching
            if file_type in self.text_manager.loaders:
                text_files.append(file)
            elif file_type in self.image_manager.loaders:
                image_files.append(file)
            else:
                unsupported_files.append(file)

        return text_files, image_files, unsupported_files

    def supported_extensions(self) -> set[str]:
        return self.text_manager.loaders.keys() | self.image_manager.loaders.keys()

    def load(self, file_path: str) -> list[dict]:
        text_files, image_files, unsupported_files = self.partition_files(file_path)

        if unsupported_files:
            unsupported_files_warning(unsupported_files, list(self.supported_extensions()))

        messages = []
        if text_files:
            messages.append({"role": "system", "content": self.text_manager.load(text_files)})
        if image_files:
            message = {"role": "system", "content": []}
            for content in self.image_manager.load(image_files):
                message['content'].append({"type": "image_url", "image_url": {"url": content}})
            messages.append(message)
        return messages
