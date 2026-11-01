"""The one result type every check returns (validation, lint rules)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    """How bad a diagnostic is. ``error`` makes ``validate``/``lint`` exit with 1."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Diagnostic:
    """One finding: ``Diagnostic(rule_id, severity, pos, message, suggestion)``.

    ``pos`` is region-relative ``(x, y, z)`` (or None for file-level findings);
    ``region`` names the region when the structure has several. ``fix`` may hold
    a machine-readable edit plan (phase 04+).
    """

    rule_id: str
    severity: Severity
    pos: tuple[int, int, int] | None
    message: str
    suggestion: str | None = None
    region: str | None = None
    fix: dict[str, Any] | None = field(default=None, compare=False)

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready representation."""
        out: dict[str, Any] = {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "pos": list(self.pos) if self.pos is not None else None,
            "message": self.message,
            "suggestion": self.suggestion,
        }
        if self.region is not None:
            out["region"] = self.region
        if self.fix is not None:
            out["fix"] = self.fix
        return out

    def format(self) -> str:
        """One human-readable line (plus the suggestion, if any)."""
        where = "" if self.pos is None else " at ({},{},{})".format(*self.pos)
        line = f"{self.severity.value}: {self.rule_id}{where}: {self.message}"
        if self.suggestion:
            line += f"\n  suggestion: {self.suggestion}"
        return line


def has_errors(diagnostics: list[Diagnostic]) -> bool:
    """True when any diagnostic has severity ``error``."""
    return any(d.severity is Severity.ERROR for d in diagnostics)
