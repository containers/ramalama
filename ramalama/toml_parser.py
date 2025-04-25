"""
A simple TOML parser that can parse TOML strings and files.
It supports sections, key-value pairs, strings, integers, floats, booleans,
and arrays.
"""
import re


class TOMLParser:
    """
    A simple TOML parser class that can parse TOML strings and files.
    """
    def __init__(self):
        """
        Initializes the TOMLParser instance.
        """
        self.data = {}

    def parse(self, toml_string):
        """
        Parses a TOML string and returns the data attribute with the parsed data.
        """
        current_section = self.data
        for line in toml_string.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("[") and line.endswith("]"):
                section_name = line[1:-1].strip()
                current_section = self._create_section(section_name)
            elif "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = self._parse_value(value.strip())
                current_section[key] = value
            else:
                raise ValueError(f"Invalid TOML line: {line}")

        return self.data

    def parse_file(self, file_path):
        """
        Parses a TOML file and returns the data attribute with the parsed data.
        """
        with open(file_path, "r") as f:
            toml_string = f.read()
        self.parse(toml_string)

        return self.data

    def _create_section(self, section_name):
        """
        Creates a section in the data dictionary based on the section name.
        """
        keys = section_name.split(".")
        section = self.data
        for key in keys:
            if key not in section:
                section[key] = {}
            section = section[key]

        return section

    def _parse_value(self, value):
        """
        Parses a value from a TOML string and returns the appropriate Python type.
        """
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        if value.startswith("[") and value.endswith("]"):
            return [self._parse_value(v.strip()) for v in value[1:-1].split(",")]
        if re.match(r'^\d+$', value):
            return int(value)
        if re.match(r'^\d+\.\d+$', value):
            return float(value)
        if value.lower() in {"true", "false"}:
            return value.lower() == "true"
        raise ValueError(f"Unsupported value type: {value}")

    def get(self, key, default=None):
        """
        Retrieves a value from the parsed data using a dot-separated key.
        If the key does not exist, returns the default value.
        """
        keys = key.split(".")
        value = self.data
        for k in keys:
            value = value.get(k)
            if value is None:
                return default

        return value
