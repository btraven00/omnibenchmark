"""
Version utility module for version string operations.

This module provides utilities for working with semantic versions,
without any dependency on the model or YAML serialization.
"""

from typing import Tuple, Optional
import re


class Version:
    """
    A semantic version representation.

    This class handles version comparison and manipulation.
    Version format: x.y.z or x.y (where x, y, z are non-negative integers)
    """

    def __init__(self, version_string: str):
        """
        Initialize a Version from a string.

        Args:
            version_string: Version string in format "x.y.z" or "x.y"

        Raises:
            ValueError: If version string is invalid
        """
        self.version_string = str(version_string).strip()
        self.major, self.minor, self.patch = self._parse_version(self.version_string)

    def _parse_version(self, version_string: str) -> Tuple[int, int, Optional[int]]:
        """Parse a version string into major, minor, patch components."""
        # Handle numeric inputs (float/int from YAML)
        if isinstance(version_string, (int, float)):
            version_string = str(version_string)

        # Match semantic version pattern
        pattern = r"^(\d+)\.(\d+)(?:\.(\d+))?$"
        match = re.match(pattern, version_string)

        if not match:
            raise ValueError(
                f"Invalid version format: '{version_string}'. Expected x.y.z or x.y"
            )

        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3)) if match.group(3) else None

        return major, minor, patch

    def __str__(self) -> str:
        """Return the string representation of the version."""
        if self.patch is None:
            return f"{self.major}.{self.minor}"
        return f"{self.major}.{self.minor}.{self.patch}"

    def __repr__(self) -> str:
        """Return the debug representation of the version."""
        return f"Version('{str(self)}')"

    def __eq__(self, other) -> bool:
        """Check if two versions are equal."""
        if not isinstance(other, Version):
            return False
        return (self.major, self.minor, self.patch) == (
            other.major,
            other.minor,
            other.patch,
        )

    def __lt__(self, other) -> bool:
        """Check if this version is less than another."""
        if not isinstance(other, Version):
            return NotImplemented

        # Compare major
        if self.major != other.major:
            return self.major < other.major

        # Compare minor
        if self.minor != other.minor:
            return self.minor < other.minor

        # Compare patch (None is treated as 0)
        self_patch = self.patch if self.patch is not None else 0
        other_patch = other.patch if other.patch is not None else 0
        return self_patch < other_patch

    def __le__(self, other) -> bool:
        """Check if this version is less than or equal to another."""
        return self == other or self < other

    def __gt__(self, other) -> bool:
        """Check if this version is greater than another."""
        if not isinstance(other, Version):
            return NotImplemented
        return not self <= other

    def __ge__(self, other) -> bool:
        """Check if this version is greater than or equal to another."""
        return self == other or self > other

    def __hash__(self) -> int:
        """Return hash of the version for use in sets/dicts."""
        return hash((self.major, self.minor, self.patch))

    def increment_minor(self) -> "Version":
        """Return a new Version with incremented minor version."""
        return Version(f"{self.major}.{self.minor + 1}")

    def increment_major(self) -> "Version":
        """Return a new Version with incremented major version."""
        return Version(f"{self.major + 1}.0")

    def increment_patch(self) -> "Version":
        """Return a new Version with incremented patch version."""
        if self.patch is None:
            return Version(f"{self.major}.{self.minor}.1")
        return Version(f"{self.major}.{self.minor}.{self.patch + 1}")


def parse_version(version_string: str) -> Version:
    """
    Parse a version string into a Version object.

    Args:
        version_string: Version string to parse

    Returns:
        Version object

    Raises:
        ValueError: If version string is invalid
    """
    return Version(version_string)


def increment_version(version: str, component: str = "minor") -> str:
    """
    Increment a version string.

    Args:
        version: Current version string
        component: Which component to increment ("major", "minor", or "patch")

    Returns:
        Incremented version string

    Raises:
        ValueError: If version string is invalid or component is unknown
    """
    v = Version(version)

    if component == "major":
        new_v = v.increment_major()
    elif component == "minor":
        new_v = v.increment_minor()
    elif component == "patch":
        new_v = v.increment_patch()
    else:
        raise ValueError(f"Unknown version component: {component}")

    return str(new_v)


def compare_versions(version1: str, version2: str) -> int:
    """
    Compare two version strings.

    Args:
        version1: First version string
        version2: Second version string

    Returns:
        -1 if version1 < version2
         0 if version1 == version2
         1 if version1 > version2

    Raises:
        ValueError: If either version string is invalid
    """
    v1 = Version(version1)
    v2 = Version(version2)

    if v1 < v2:
        return -1
    elif v1 > v2:
        return 1
    else:
        return 0
