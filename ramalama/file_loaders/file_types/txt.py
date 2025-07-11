from ramalama.file_loaders.file_types.base import BaseFileLoader


class TXTFileLoader(BaseFileLoader):
    @staticmethod
    def file_extensions() -> set[str]:
        return {
            ".txt",
            ".sh",
            ".md",
            ".yaml",
            ".yml",
            ".json",
            ".csv",
            ".toml",
        }

    @staticmethod
    def load(file: str) -> str:
        """
        Load the content of the text file.
        """

        # TODO: Support for non-default encodings?
        with open(file, "r") as f:
            return f.read()
