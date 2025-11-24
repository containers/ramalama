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
    config_fields.extend(('http_client', 'images', 'rag_images', 'user'))
    return sorted(set(config_fields))


def get_documented_fields_in_conf():
    """Extract documented field names from docs/ramalama.conf."""
    conf_path = Path(__file__).parent.parent.parent / "docs" / "ramalama.conf"

    if not conf_path.exists():
        pytest.skip(f"ramalama.conf not found at {conf_path}")

    with open(conf_path) as f:
        lines = f.readlines()

    # Match commented and uncommented config options like:
    # #api = "none"
    # api_key = ""
    # [ramalama.images]
    pattern = r'^\s*#?\s*([a-z_]+)\s*='
    documented = set()

    # Subsections that contain their own field documentation (these fields should not be extracted)
    subsections_with_fields = {'http_client', 'user'}

    # Track which section we're in to exclude nested fields under commented subsections
    in_commented_nested_section = False
    section_pattern = r'^\s*(#?)\s*\[ramalama\.([a-z_]+)\]'
    main_section_pattern = r'^\s*\[ramalama\]'
    prev_line_blank = False

    for line in lines:
        current_line_blank = line.strip() == ''

        # Check if we're at the main [ramalama] section
        if re.match(main_section_pattern, line):
            in_commented_nested_section = False
            prev_line_blank = current_line_blank
            continue

        # Check if we're entering a subsection
        section_match = re.match(section_pattern, line)
        if section_match:
            is_commented = section_match.group(1) == '#'
            section_name = section_match.group(2)
            documented.add(section_name)
            # Skip fields if it's a commented nested section OR if it's a subsection with its own fields
            in_commented_nested_section = is_commented or (section_name in subsections_with_fields)
            prev_line_blank = current_line_blank
            continue

        # Check if we hit a new uncommented section (which ends any nested section)
        if re.match(r'^\s*\[', line) and not line.strip().startswith('#'):
            in_commented_nested_section = False

        # If we're in a commented subsection, stay in it until we see a clear exit point
        # Exit point: blank line followed by a comment that starts a new field's documentation
        if in_commented_nested_section:
            # If this line has a field definition, skip it
            if '=' in line:
                prev_line_blank = current_line_blank
                continue
            # If previous line was blank and this is a comment (but not empty), might be exiting
            elif prev_line_blank and line.strip().startswith('#') and line.strip() not in ['#', '']:
                # This looks like the start of a new field's documentation, exit
                in_commented_nested_section = False
            # Otherwise stay in the section
            else:
                prev_line_blank = current_line_blank
                continue

        # Only match fields when not in a commented nested subsection
        if not in_commented_nested_section:
            match = re.match(pattern, line)
            if match:
                field_name = match.group(1)
                documented.add(field_name)

        prev_line_blank = current_line_blank

    return sorted(documented)


def get_documented_fields_in_manpage():
    """Extract documented field names from docs/ramalama.conf.5.md."""
    manpage_path = Path(__file__).parent.parent.parent / "docs" / "ramalama.conf.5.md"

    if not manpage_path.exists():
        pytest.skip(f"ramalama.conf.5.md not found at {manpage_path}")

    with open(manpage_path) as f:
        lines = f.readlines()

    # Match markdown bold options like:
    # **api**="none"
    # **api_key**=""
    # But exclude option values like **always**, **missing**, etc. which appear in pull documentation
    pattern = r'^\*\*([a-z_]+)\*\*'

    # Ignore values, not config keys
    ignored_values = {'always', 'missing', 'never', 'newer'}
    documented = set()

    # Subsections that contain their own **field** documentation (these fields should not be extracted)
    subsections_with_fields = {'http_client', 'user'}

    # Track which section we're in
    current_section = None
    main_section_pattern = r'^`\[\[ramalama\]\]`$'
    section_pattern = r'^`\[\[ramalama\.([a-z_]+)\]\]`'
    in_main_section = False

    for line in lines:
        # Check if we're entering the main [[ramalama]] section
        if re.match(main_section_pattern, line):
            in_main_section = True
            current_section = None
            continue

        # Check if we're entering a subsection like [[ramalama.images]]
        section_match = re.match(section_pattern, line)
        if section_match:
            section_name = section_match.group(1)
            current_section = section_name
            documented.add(section_name)
            continue

        # Reset section when we hit a new top-level heading
        if line.startswith('## '):
            if 'RAMALAMA TABLE' in line.upper():
                in_main_section = False
                current_section = None
            else:
                # Hitting a new ## heading ends any subsection
                in_main_section = False
                current_section = None

        # When we're in the main [[ramalama]] section
        if in_main_section:
            match = re.match(pattern, line)
            if match:
                field = match.group(1)
                if field not in ignored_values:
                    # If we're in a subsection that has its own field documentation,
                    # skip those fields (they're not top-level config options)
                    if current_section in subsections_with_fields:
                        continue

                    # If we found a field while in another kind of subsection (like images),
                    # it means we're back in the main section
                    if current_section is not None:
                        current_section = None
                    documented.add(field)

    return sorted(documented)


class TestConfigDocumentation:
    """Test suite to ensure CONFIG options are properly documented."""

    # Aliases and special cases that are documented but map to actual fields
    KNOWN_ALIASES = {
        'default_image',  # Alias for 'image' configuration
        'default_rag_image',  # Alias for rag image configuration
        'no_missing_gpu_prompt',  # Nested field under user.no_missing_gpu_prompt
    }

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

        extra = set(documented_fields) - set(config_fields) - self.KNOWN_ALIASES

        assert not extra, (
            f"The following fields are documented in docs/ramalama.conf but not in CONFIG:\n"
            f"{', '.join(sorted(extra))}\n\n"
            f"These might be typos or outdated documentation."
        )

    def test_no_undocumented_fields_in_manpage(self):
        """Verify ramalama.conf.5.md doesn't document non-existent fields."""
        config_fields = get_config_fields()
        documented_fields = get_documented_fields_in_manpage()

        extra = set(documented_fields) - set(config_fields) - self.KNOWN_ALIASES

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
