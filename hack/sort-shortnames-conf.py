#!/usr/bin/env python3
"""Sort shortnames.conf entries by model family and version number.

Preserves comment lines and the [shortnames] header at the top of the file.
Each entry line is sorted using a version-aware key derived from the shortname
(e.g. qwen2 < qwen2.5 < qwen3 < qwen3.5 < qwen3.6, llama3 < llama3.1).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ENTRY_RE = re.compile(r'^(\s*)"([^"]+)"\s*=\s*(.+)$')
VERSION_RE = re.compile(r"\d+(?:\.\d+)*")
SIZE_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)")


def version_sort_key(shortname: str) -> tuple:
    """Build a sort key from a shortname like qwen3.6:35b or llama3.1:8b."""
    base, _, size = shortname.partition(":")
    # Treat gemma-4 and gemma4 (etc.) as the same family for ordering.
    normalized = base.replace("-", "")
    parts: list[tuple] = []
    for piece in re.split(f"({VERSION_RE.pattern})", normalized):
        if not piece:
            continue
        if VERSION_RE.fullmatch(piece):
            ver = tuple(int(x) for x in piece.split("."))
            parts.append((1, ver))
        else:
            parts.append((0, piece.lower()))
    parts.append((2,) + _size_sort_key(size))
    parts.append((3, shortname.lower()))
    return tuple(parts)


def _size_sort_key(size: str) -> tuple:
    if not size:
        return (0, 0.0, "")
    match = SIZE_NUM_RE.search(size)
    if match:
        return (1, float(match.group(1)), size.lower())
    return (2, 0.0, size.lower())


def parse_sections(lines: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """Return (header lines including [shortnames], list of (line, key))."""
    header: list[str] = []
    entries: list[tuple[str, str]] = []
    in_entries = False

    for line in lines:
        if not in_entries:
            header.append(line)
            if line.strip() == "[shortnames]":
                in_entries = True
            continue

        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        match = ENTRY_RE.match(line)
        if not match:
            raise ValueError(f"unexpected line in [shortnames] section: {line!r}")

        key = match.group(2)
        entries.append((line, key))

    if not in_entries:
        raise ValueError("missing [shortnames] section")

    return header, entries


def sort_shortnames_conf(text: str) -> str:
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"

    header, entries = parse_sections(lines)
    sorted_entries = sorted(entries, key=lambda item: version_sort_key(item[1]))
    body = "".join(line for line, _ in sorted_entries)
    return "".join(header) + body


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    default_path = repo_root / "shortnames" / "shortnames.conf"

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=default_path,
        help=f"path to shortnames.conf (default: {default_path})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the file would change (for CI)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="write sorted output here instead of overwriting path",
    )
    args = parser.parse_args()

    path = args.path.resolve()
    original = path.read_text(encoding="utf-8")
    sorted_text = sort_shortnames_conf(original)

    if args.check:
        if sorted_text != original:
            print(f"{path}: shortnames are not sorted (run hack/sort-shortnames-conf.py)", file=sys.stderr)
            return 1
        print(f"{path}: OK")
        return 0

    output_path = args.output.resolve() if args.output else path
    output_path.write_text(sorted_text, encoding="utf-8")
    if output_path == path:
        print(f"Sorted {path}")
    else:
        print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
