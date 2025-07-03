from abc import ABC, abstractmethod


class BaseFileLoader(ABC):
    """
    Base class for file upload handlers.
    This class should be extended by specific file type handlers.
    """

    @staticmethod
    @abstractmethod
    def load(file: str) -> str:
        """
        Load the content of the file.
        This method should be implemented by subclasses to handle specific file types.
        """
        pass

    @staticmethod
    @abstractmethod
    def file_extensions() -> set[str]:
        """
        Get the file extension supported by this file type handler.
        """
        pass
