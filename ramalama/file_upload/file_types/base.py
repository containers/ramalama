from abc import ABC, abstractmethod


class BaseFileUpload(ABC):
    """
    Base class for file upload handlers.
    This class should be extended by specific file type handlers.
    """

    def __init__(self, file):
        self.file = file

    @abstractmethod
    def load(self) -> str:
        """
        Load the content of the file.
        This method should be implemented by subclasses to handle specific file types.
        """
        pass
