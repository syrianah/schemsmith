"""Apply the edit plans attached to diagnostics (``Diagnostic.fix``).

A fix is an edit plan (see :mod:`schemsmith.core.edits`) plus a ``description``.
"""

from __future__ import annotations

from typing import Any

from schemsmith.core import Structure
from schemsmith.core.edits import EditResult, apply_plan


def apply_fix(structure: Structure, fix: dict[str, Any]) -> EditResult:
    """Apply one fix in place. Raises ``ValueError`` (:class:`EditError`) when it is invalid."""
    return apply_plan(structure, fix)


__all__ = ["apply_fix"]
