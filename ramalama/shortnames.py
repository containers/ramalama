import configparser
import os
import sysconfig


class Shortnames:
    """Shortnames utility class"""

    shortnames: dict[str, str] = {}

    def __init__(self):
        data_path = sysconfig.get_path("data")
        file_paths = [
            "./shortnames/shortnames.conf",  # for development
            "./shortnames.conf",  # for development
            f"{data_path}/share/ramalama/shortnames.conf",
        ]

        if os.name == 'nt':
            # Windows-specific paths using APPDATA and LOCALAPPDATA
            appdata = os.getenv("APPDATA", os.path.expanduser("~/AppData/Roaming"))
            localappdata = os.getenv("LOCALAPPDATA", os.path.expanduser("~/AppData/Local"))
            file_paths.extend(
                [
                    os.path.join(localappdata, "ramalama", "shortnames.conf"),
                    os.path.join(appdata, "ramalama", "shortnames.conf"),
                ]
            )
        else:
            # Unix-specific paths using XDG conventions
            file_paths.extend(
                [
                    os.path.expanduser("~/.config/ramalama/shortnames.conf"),
                    os.path.expanduser("~/.local/share/ramalama/shortnames.conf"),
                    os.path.expanduser("~/.local/pipx/venvs/ramalama/share/ramalama/shortnames.conf"),
                    "/etc/ramalama/shortnames.conf",
                    "/usr/share/ramalama/shortnames.conf",
                    "/usr/local/share/ramalama/shortnames.conf",
                ]
            )

        self.paths = []
        for file_path in file_paths:
            config = configparser.ConfigParser(delimiters="=")
            config.read(file_path)
            if "shortnames" in config:
                self.paths.append(os.path.realpath(file_path))
                self.shortnames.update(config["shortnames"])

        # Remove leading and trailing quotes from keys and values
        self.shortnames = {self._strip_quotes(key): self._strip_quotes(value) for key, value in self.shortnames.items()}

    def _strip_quotes(self, s) -> str:
        return s.strip("'\"")

    def resolve(self, model) -> str | None:
        return self.shortnames.get(model, model)
