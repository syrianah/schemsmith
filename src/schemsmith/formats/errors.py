"""Format error type."""

from __future__ import annotations


class FormatError(ValueError):
    """Raised when a file is not a valid schematic of the expected format."""
