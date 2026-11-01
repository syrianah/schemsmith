"""NBT error type."""

from __future__ import annotations


class NbtError(ValueError):
    """Raised for malformed, truncated or oversized NBT data."""
