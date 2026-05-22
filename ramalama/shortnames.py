from __future__ import annotations

import configparser
import os
import re
import sys
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

    @staticmethod
    def sort_file(file_path: str, *, check: bool = False) -> bool:
        """Sort shortnames.conf entries by key, preserving header comments.

        Returns True if file is sorted. With check=True, returns False instead of writing.
        """

        with open(file_path) as f:
            lines = f.readlines()

        header: list[str] = []
        entries: list[str] = []
        in_entries = False
        for line in lines:
            if not in_entries:
                header.append(line)
                if line.strip().lower() == '[shortnames]':
                    in_entries = True
            else:
                entries.append(line)

        def is_mapping(line: str) -> bool:
            return line.strip().startswith('"')

        def parse_key(line: str) -> str:
            s = line.strip()
            return s[1 : s.index('"', 1)]

        def parse_tag_as_numeric(tag: str) -> float | None:
            multipliers = {'b': 1e9, 'm': 1e6, 'k': 1e3}
            m = re.search(r'(\d+)x(\d+\.?\d*)([bmk])\b', tag, re.IGNORECASE)
            if m:
                return float(m.group(1)) * float(m.group(2)) * multipliers[m.group(3).lower()]
            m = re.search(r'(\d+\.?\d*)([bmk])\b', tag, re.IGNORECASE)
            if m:
                return float(m.group(1)) * multipliers[m.group(2).lower()]
            m = re.search(r'(\d+\.?\d*)', tag)
            if m:
                return float(m.group(1))
            return None

        def entry_sort_key(line: str) -> tuple:
            key = parse_key(line)
            tag = key.split(':', 1)[1] if ':' in key else ''
            num = parse_tag_as_numeric(tag)
            return (num is not None, num, tag if num is None else '')

        def entry_name(line: str) -> str:
            key = parse_key(line)
            return key.split(':')[0] if ':' in key else key

        mappings = [line for line in entries if is_mapping(line)]
        # Pass 1: sort by tag — non-numeric tags first (lexically), then numeric tags by value
        sorted_mappings = sorted(mappings, key=entry_sort_key)
        # Pass 2: stable sort lexically by name
        sorted_mappings = sorted(sorted_mappings, key=entry_name)

        if mappings == sorted_mappings:
            return True

        if check:
            return False

        it = iter(sorted_mappings)
        result = [next(it) if is_mapping(line) else line for line in entries]

        with open(file_path, 'w') as f:
            f.writelines(header)
            f.writelines(result)

        return True


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    check = "--check" in sys.argv[1:]
    if len(args) != 1:
        print(f"Usage: {sys.argv[0]} [--check] <conf-file>", file=sys.stderr)
        sys.exit(2)
    if not Shortnames.sort_file(args[0], check=check):
        print(f"ERROR: {args[0]} is not sorted by key. Run 'make format' to fix.", file=sys.stderr)
        sys.exit(1)
