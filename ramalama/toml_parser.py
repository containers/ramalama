from __future__ import annotations

import re

from ramalama.logger import logger


class TOMLParser:
    def __init__(self):
        self.data = {}

    def parse(self, toml_string):
        current_section = self.data
        for line in toml_string.splitlines():
            line = self._strip_comment(line).strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("[") and line.endswith("]"):
                section_name = line[1:-1].strip()
                current_section = self._create_section(section_name)
            elif "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = self._parse_value(value.strip())
                # We are parsing multiple TOML files,
                # if there are duplicate keys from previous files, we just overwrite them
                if key in current_section:
                    logger.debug(f"Duplicate key found: {key}")
                current_section[key] = value
            else:
                raise ValueError(f"Invalid TOML line: {line}")

        return self.data

    def parse_file(self, file_path):
        # utf-8-sig drops the BOM that some Windows editors write
        with open(file_path, "r", encoding="utf-8-sig") as f:
            toml_string = f.read()
        self.parse(toml_string)

        return self.data

    @staticmethod
    def _strip_comment(line):
        """Remove a trailing ``# comment`` that is not inside a string."""
        quote = None
        escaped = False
        for i, char in enumerate(line):
            if escaped:
                escaped = False
            elif quote == '"' and char == "\\":
                escaped = True
            elif quote:
                if char == quote:
                    quote = None
            elif char in ('"', "'"):
                quote = char
            elif char == "#":
                return line[:i]
        return line

    def _create_section(self, section_name):
        keys = section_name.split(".")
        section = self.data
        for key in keys:
            if key not in section:
                section[key] = {}
            section = section[key]

        return section

    def _parse_value(self, value):
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
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
        keys = key.split(".")
        value: object = self.data
        for k in keys:
            if not isinstance(value, dict):
                return default
            value = value.get(k)
            if value is None:
                return default

        return value
