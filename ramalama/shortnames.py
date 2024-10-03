import configparser
import os


class Shortnames:
    """Shortnames utility class"""

    shortnames = {}

    def __init__(self):
        file_paths = [
            "/usr/share/ramalama/shortnames.conf",
            "/etc/ramalama/shortnames.conf",
            os.path.expanduser("~/.local/share/ramalama/shortnames.conf"),
            os.path.expanduser("~/.config/ramalama/shortnames.conf"),
            "./shortnames/shortnames.conf",  # for development
            "./shortnames.conf",  # for development
        ]

        for file_path in file_paths:
            config = configparser.ConfigParser(delimiters=("="))
            config.read(file_path)
            if "shortnames" in config:
                self.shortnames.update(config["shortnames"])

        # Remove leading and trailing quotes from keys and values
        self.shortnames = {self._strip_quotes(key): self._strip_quotes(value) for key, value in self.shortnames.items()}

    def _strip_quotes(self, s):
        return s.strip("'\"")

    def resolve(self, model):
        return self.shortnames.get(model)
