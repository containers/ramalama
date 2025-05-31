import configparser
import os
import sysconfig
import tempfile


class Shortnames:
    """Shortnames utility class"""

    shortnames = {}

    def __init__(self):
        data_path = sysconfig.get_path("data")
        file_paths = [
            "./shortnames/shortnames.conf",  # for development
            "./shortnames.conf",  # for development
            os.path.expanduser("~/.config/ramalama/shortnames.conf"),
            f"{data_path}/share/ramalama/shortnames.conf",
            os.path.expanduser("~/.local/share/ramalama/shortnames.conf"),
            os.path.expanduser("~/.local/pipx/venvs/ramalama/share/ramalama/shortnames.conf"),
            "/etc/ramalama/shortnames.conf",
            "/usr/share/ramalama/shortnames.conf",
            "/usr/local/share/ramalama/shortnames.conf",
        ]

        self.paths = []
        for file_path in file_paths:
            config = configparser.ConfigParser(delimiters="=")
            config.read(file_path)
            if "shortnames" in config:
                self.paths.append(os.path.realpath(file_path))
                self.shortnames.update(config["shortnames"])

        # Remove leading and trailing quotes from keys and values
        self.shortnames = {self._strip_quotes(key): self._strip_quotes(value) for key, value in self.shortnames.items()}

    def _strip_quotes(self, s):
        return s.strip("'\"")

    def resolve(self, model):
        return self.shortnames.get(model)

    def create_shortname_file(self):
        shortnamefile = tempfile.NamedTemporaryFile(prefix='RamaLama_shortname_', delete=False)
        # Open the file for writing.
        with open(shortnamefile.name, 'w') as c:
            c.write('[shortnames]\n')
            for shortname in self.shortnames:
                c.write('"%s"="%s"\n' % (shortname, self.shortnames.get(shortname)))
            c.flush()
        return shortnamefile.name
