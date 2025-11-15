"""
Test to ensure all CONFIG options are properly documented in ramalama.conf and ramalama.conf.5.md
"""

import re
from dataclasses import fields
from pathlib import Path

import pytest

from ramalama.config import BaseConfig


def get_config_fields():
    """Extract all field names from BaseConfig dataclass, excluding internal/system fields."""
    excluded_fields = {
        'settings',  # Internal RamalamaSettings, not user-configurable
        'default_image',  # Internal constant, users configure 'image' instead
        'default_rag_image',  # Internal constant, users configure 'rag_image' instead
        'rag_image',  # Derived from rag_images, not directly configured
        'stack_image',  # Internal constant for stack operations
        'dryrun',  # Runtime flag, not a persistent config option
        'ocr',  # Runtime flag, not a persistent config option
        'verify',  # Runtime flag for model verification, not typically configured
    }

    config_fields = [field.name for field in fields(BaseConfig) if field.name not in excluded_fields]
    config_fields.extend(('images', 'rag_images', 'user'))
    return sorted(set(config_fields))


def get_documented_fields_in_conf():
    """Extract documented field names from docs/ramalama.conf."""
    conf_path = Path(__file__).parent.parent.parent / "docs" / "ramalama.conf"

    if not conf_path.exists():
        pytest.skip(f"ramalama.conf not found at {conf_path}")

    with open(conf_path) as f:
        content = f.read()

    # Match commented and uncommented config options like:
    # #api = "none"
    # api_key = ""
    # [ramalama.images]
    pattern = r'^\s*#?\s*([a-z_]+)\s*='
    documented = set()

    for line in content.split('\n'):
        match = re.match(pattern, line)
        if match:
            field_name = match.group(1)
            documented.add(field_name)

    # Also check for section headers like [ramalama.images]
    section_pattern = r'^\s*#?\s*\[ramalama\.([a-z_]+)\]'
    for line in content.split('\n'):
        match = re.match(section_pattern, line)
        if match:
            field_name = match.group(1)
            documented.add(field_name)

    return sorted(documented)


def get_documented_fields_in_manpage():
    """Extract documented field names from docs/ramalama.conf.5.md."""
    manpage_path = Path(__file__).parent.parent.parent / "docs" / "ramalama.conf.5.md"

    if not manpage_path.exists():
        pytest.skip(f"ramalama.conf.5.md not found at {manpage_path}")

    with open(manpage_path) as f:
        content = f.read()

    # Match markdown bold options like:
    # **api**="none"
    # **api_key**=""
    # But exclude option values like **always**, **missing**, etc. which appear in pull documentation
    pattern = r'^\*\*([a-z_]+)\*\*'
    all_matches = re.findall(pattern, content, re.MULTILINE)

    # Ignore values, not config keys
    ignored_values = {'always', 'missing', 'never', 'newer'}
    documented = {field for field in all_matches if field not in ignored_values}

    # Also check for section headers like `[[ramalama.images]]`
    section_pattern = r'`\[\[ramalama\.([a-z_]+)\]\]`'
    documented.update(re.findall(section_pattern, content))

    return sorted(documented)


class TestConfigDocumentation:
    """Test suite to ensure CONFIG options are properly documented."""

    def test_config_fields_in_ramalama_conf(self):
        """Verify all CONFIG fields are documented in ramalama.conf."""
        config_fields = get_config_fields()
        documented_fields = get_documented_fields_in_conf()

        missing = set(config_fields) - set(documented_fields)

        assert not missing, (
            f"The following CONFIG fields are missing from docs/ramalama.conf:\n"
            f"{', '.join(sorted(missing))}\n\n"
            f"Please add documentation for these fields in docs/ramalama.conf"
        )

    def test_config_fields_in_manpage(self):
        """Verify all CONFIG fields are documented in ramalama.conf.5.md."""
        config_fields = get_config_fields()
        documented_fields = get_documented_fields_in_manpage()

        missing = set(config_fields) - set(documented_fields)

        assert not missing, (
            f"The following CONFIG fields are missing from docs/ramalama.conf.5.md:\n"
            f"{', '.join(sorted(missing))}\n\n"
            f"Please add documentation for these fields in docs/ramalama.conf.5.md"
        )

    def test_no_undocumented_fields_in_conf(self):
        """Verify ramalama.conf doesn't document non-existent fields."""
        config_fields = get_config_fields()
        documented_fields = get_documented_fields_in_conf()

        # Some aliases and special cases that are documented but map to actual fields
        known_aliases = {
            'default_image',  # Alias for 'image' configuration
            'default_rag_image',  # Alias for rag image configuration
        }

        extra = set(documented_fields) - set(config_fields) - known_aliases

        assert not extra, (
            f"The following fields are documented in docs/ramalama.conf but not in CONFIG:\n"
            f"{', '.join(sorted(extra))}\n\n"
            f"These might be typos or outdated documentation."
        )

    def test_no_undocumented_fields_in_manpage(self):
        """Verify ramalama.conf.5.md doesn't document non-existent fields."""
        config_fields = get_config_fields()
        documented_fields = get_documented_fields_in_manpage()

        # Some aliases and special cases that are documented but map to actual fields
        known_aliases = {
            'default_image',  # Alias for 'image' configuration
            'default_rag_image',  # Alias for rag image configuration
        }

        extra = set(documented_fields) - set(config_fields) - known_aliases

        assert not extra, (
            f"The following fields are documented in docs/ramalama.conf.5.md but not in CONFIG:\n"
            f"{', '.join(sorted(extra))}\n\n"
            f"These might be typos or outdated documentation."
        )

    def test_consistency_between_conf_and_manpage(self):
        """Verify both documentation files document the same fields."""
        conf_fields = get_documented_fields_in_conf()
        manpage_fields = get_documented_fields_in_manpage()

        only_in_conf = set(conf_fields) - set(manpage_fields)
        only_in_manpage = set(manpage_fields) - set(conf_fields)

        error_msg = []
        if only_in_conf:
            error_msg.append(f"Fields documented only in ramalama.conf:\n{', '.join(sorted(only_in_conf))}")
        if only_in_manpage:
            error_msg.append(f"Fields documented only in ramalama.conf.5.md:\n{', '.join(sorted(only_in_manpage))}")

        assert not error_msg, (
            "Documentation inconsistency between ramalama.conf and ramalama.conf.5.md:\n\n"
            + "\n\n".join(error_msg)
            + "\n\nBoth files should document the same configuration options."
        )
