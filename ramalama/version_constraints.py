"""Version parsing and constraint matching for hardware compatibility."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, TypeAlias

VersionOperator: TypeAlias = Literal[">=", "<=", "==", ">", "<", "!="]


@dataclass(frozen=True)
class Version:
    """Represents a semantic version (major.minor.patch)."""

    major: int
    minor: int = 0
    patch: int = 0

    @classmethod
    def from_string(cls, version_str: str) -> "Version":
        """
        Parse version string like '12.4', '12.4.1', '6.3.0'.

        Args:
            version_str: Version string to parse

        Returns:
            Version object with major, minor, patch components
        """
        parts = version_str.strip().split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return cls(major, minor, patch)

    @classmethod
    def from_tuple(cls, version_tuple: tuple[int, ...]) -> "Version":
        """
        Create Version from a tuple like (12, 4) or (12, 4, 1).

        Args:
            version_tuple: Tuple of version components

        Returns:
            Version object
        """
        major = version_tuple[0] if len(version_tuple) > 0 else 0
        minor = version_tuple[1] if len(version_tuple) > 1 else 0
        patch = version_tuple[2] if len(version_tuple) > 2 else 0
        return cls(major, minor, patch)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def as_tuple(self) -> tuple[int, int, int]:
        """Return version as (major, minor, patch) tuple for comparison."""
        return (self.major, self.minor, self.patch)


@dataclass
class VersionConstraint:
    """Represents a single version constraint like '>=12.4' or '<13.0'."""

    operator: VersionOperator
    version: Version

    @classmethod
    def from_string(cls, constraint_str: str) -> "VersionConstraint":
        """
        Parse constraint string like '>=12.4', '==6.3.0'.

        Args:
            constraint_str: Constraint string with operator and version

        Returns:
            VersionConstraint object

        Raises:
            ValueError: If constraint string is invalid
        """
        match = re.match(r"^(>=|<=|==|>|<|!=)(.+)$", constraint_str.strip())
        if not match:
            raise ValueError(f"Invalid version constraint: {constraint_str}")
        operator: VersionOperator = match.group(1)  # type: ignore[assignment]
        version = Version.from_string(match.group(2))
        return cls(operator=operator, version=version)

    def matches(self, version: Version) -> bool:
        """
        Check if a version satisfies this constraint.

        Args:
            version: Version to check against constraint

        Returns:
            True if version satisfies the constraint
        """
        v1, v2 = version.as_tuple(), self.version.as_tuple()
        match self.operator:
            case ">=":
                return v1 >= v2
            case "<=":
                return v1 <= v2
            case "==":
                return v1 == v2
            case ">":
                return v1 > v2
            case "<":
                return v1 < v2
            case "!=":
                return v1 != v2
        return False


@dataclass
class VersionRange:
    """
    Represents a version range with multiple constraints.

    Examples:
        - ">=12.4,<13.0" - CUDA 12.4 to 12.x
        - ">=5.4" - ROCm 5.4 or higher
        - "*" - Any version
    """

    constraints: list[VersionConstraint]

    @classmethod
    def from_string(cls, range_str: str) -> "VersionRange":
        """
        Parse range string like '>=12.4,<13.0' or single constraint '>=12.4'.

        Args:
            range_str: Version range string, "*" or "" for any version

        Returns:
            VersionRange object
        """
        if not range_str or range_str.strip() == "*":
            return cls(constraints=[])  # Matches any version
        parts = [p.strip() for p in range_str.split(",")]
        constraints = [VersionConstraint.from_string(p) for p in parts if p]
        return cls(constraints=constraints)

    def matches(self, version: Version | None) -> bool:
        """
        Check if a version satisfies all constraints.

        Empty constraints match any version. None version only matches
        if constraints are empty (any version acceptable).

        Args:
            version: Version to check, or None if unknown

        Returns:
            True if version satisfies all constraints
        """
        if not self.constraints:
            return True  # No constraints means any version is acceptable
        if version is None:
            return False  # Can't match specific constraints if version is unknown
        return all(c.matches(version) for c in self.constraints)

    def __str__(self) -> str:
        if not self.constraints:
            return "*"
        return ",".join(f"{c.operator}{c.version}" for c in self.constraints)
