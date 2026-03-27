import configparser
import os
import sysconfig


class Shortnames:
    """Shortnames utility class"""

    shortnames: dict[str, str] = {}
    config_sources: dict[str, str] = {}

    def __init__(self):
        self.shortnames = {}
        self.config_sources = {}
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
                    os.path.expanduser(
                        os.path.join(os.getenv("XDG_CONFIG_HOME", "~/.config"), "ramalama/shortnames.conf")
                    ),
                    os.path.expanduser(
                        os.path.join(os.getenv("XDG_DATA_HOME", "~/.local/share"), "ramalama/shortnames.conf")
                    ),
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
                real_path = os.path.realpath(file_path)
                self.paths.append(real_path)
                for key, value in config["shortnames"].items():
                    name = self._strip_quotes(key)
                    target = self._strip_quotes(value)
                    self.shortnames[name] = target
                    self.config_sources[name] = real_path

    def _strip_quotes(self, s) -> str:
        return s.strip("'\"")

    def resolve(self, model: str) -> str:
        return self.shortnames.get(model, model)
