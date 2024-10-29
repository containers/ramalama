import re


class TOMLParser:
    def __init__(self):
        self.data = {}

    def parse(self, toml_string):
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
        with open(file_path, "r") as f:
            toml_string = f.read()
        self.parse(toml_string)

        return self.data

    def _create_section(self, section_name):
        keys = section_name.split(".")
        section = self.data
        for key in keys:
            if key not in section:
                section[key] = {}
            section = section[key]

        return section

    def _parse_value(self, value):
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        elif value.startswith("[") and value.endswith("]"):
            return [self._parse_value(v.strip()) for v in value[1:-1].split(",")]
        elif re.match(r'^\d+$', value):
            return int(value)
        elif re.match(r'^\d+\.\d+$', value):
            return float(value)
        elif value.lower() in {"true", "false"}:
            return value.lower() == "true"
        else:
            raise ValueError(f"Unsupported value type: {value}")

    def get(self, key, default=None):
        keys = key.split(".")
        value = self.data
        for key in keys:
            value = value.get(key)
            if value is None:
                return default

        return value
