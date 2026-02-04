"""Unit tests for version_constraints module."""

import pytest

from ramalama.version_constraints import Version, VersionConstraint, VersionRange


class TestVersion:
    """Tests for the Version class."""

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("12.4", (12, 4, 0)),
            ("12.4.1", (12, 4, 1)),
            ("6", (6, 0, 0)),
            ("6.3.0", (6, 3, 0)),
            ("1.2.3", (1, 2, 3)),
            ("0.17", (0, 17, 0)),
            ("  12.4  ", (12, 4, 0)),  # whitespace handling
        ],
    )
    def test_from_string(self, input_str: str, expected: tuple[int, int, int]):
        v = Version.from_string(input_str)
        assert v.as_tuple() == expected

    @pytest.mark.parametrize(
        "input_tuple,expected",
        [
            ((12, 4), (12, 4, 0)),
            ((12, 4, 1), (12, 4, 1)),
            ((6,), (6, 0, 0)),
            ((), (0, 0, 0)),
        ],
    )
    def test_from_tuple(self, input_tuple: tuple[int, ...], expected: tuple[int, int, int]):
        v = Version.from_tuple(input_tuple)
        assert v.as_tuple() == expected

    def test_str_representation(self):
        v = Version(12, 4, 1)
        assert str(v) == "12.4.1"

    def test_version_comparison(self):
        v1 = Version(12, 4, 0)
        v2 = Version(12, 4, 1)
        v3 = Version(12, 5, 0)
        v4 = Version(13, 0, 0)

        assert v1.as_tuple() < v2.as_tuple()
        assert v2.as_tuple() < v3.as_tuple()
        assert v3.as_tuple() < v4.as_tuple()
        assert v1.as_tuple() == (12, 4, 0)


class TestVersionConstraint:
    """Tests for the VersionConstraint class."""

    @pytest.mark.parametrize(
        "constraint_str,version_str,expected",
        [
            # Greater than or equal
            (">=12.4", "12.4.0", True),
            (">=12.4", "12.3.0", False),
            (">=12.4", "13.0.0", True),
            (">=12.4", "12.4.1", True),
            # Less than
            ("<13.0", "12.8.0", True),
            ("<13.0", "13.0.0", False),
            ("<13.0", "13.0.1", False),
            # Less than or equal
            ("<=12.8", "12.8.0", True),
            ("<=12.8", "12.8.1", False),
            ("<=12.8", "12.7.0", True),
            # Equal
            ("==12.4", "12.4.0", True),
            ("==12.4", "12.4.1", False),
            ("==12.4.0", "12.4.0", True),
            # Greater than
            (">12.4", "12.5.0", True),
            (">12.4", "12.4.0", False),
            (">12.4", "12.4.1", True),
            # Not equal
            ("!=12.4", "12.5.0", True),
            ("!=12.4", "12.4.0", False),
        ],
    )
    def test_matches(self, constraint_str: str, version_str: str, expected: bool):
        c = VersionConstraint.from_string(constraint_str)
        v = Version.from_string(version_str)
        assert c.matches(v) == expected

    def test_invalid_constraint_raises_error(self):
        with pytest.raises(ValueError, match="Invalid version constraint"):
            VersionConstraint.from_string("invalid")

        with pytest.raises(ValueError, match="Invalid version constraint"):
            VersionConstraint.from_string("12.4")  # Missing operator


class TestVersionRange:
    """Tests for the VersionRange class."""

    @pytest.mark.parametrize(
        "range_str,version_str,expected",
        [
            # Single constraint
            (">=12.4", "12.6.0", True),
            (">=12.4", "12.3.0", False),
            # Range with AND logic
            (">=12.4,<13.0", "12.6.0", True),
            (">=12.4,<13.0", "13.0.0", False),
            (">=12.4,<13.0", "12.3.0", False),
            # Wildcard
            ("*", "1.0.0", True),
            ("*", "999.999.999", True),
            ("", "1.0.0", True),
            # Complex range
            (">=12.4,<=12.8", "12.6.0", True),
            (">=12.4,<=12.8", "12.8.0", True),
            (">=12.4,<=12.8", "12.8.1", False),
            (">=12.4,<=12.8", "12.3.0", False),
        ],
    )
    def test_matches(self, range_str: str, version_str: str, expected: bool):
        r = VersionRange.from_string(range_str)
        v = Version.from_string(version_str)
        assert r.matches(v) == expected

    def test_matches_none_version(self):
        # Wildcard should match None
        r = VersionRange.from_string("*")
        assert r.matches(None) is True

        # Specific constraint should not match None
        r = VersionRange.from_string(">=12.4")
        assert r.matches(None) is False

    def test_str_representation(self):
        r = VersionRange.from_string(">=12.4,<13.0")
        assert str(r) == ">=12.4.0,<13.0.0"

        r = VersionRange.from_string("*")
        assert str(r) == "*"
