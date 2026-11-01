"""Redstone lint rules built on the power graph.

>>> from schemsmith.redstone.lint import lint_structure  # doctest: +SKIP
"""

from __future__ import annotations

from collections.abc import Iterable

from schemsmith.core import Structure
from schemsmith.diagnostics import Diagnostic
from schemsmith.redstone.graph import PowerGraph
from schemsmith.redstone.lint.fixes import apply_fix
from schemsmith.redstone.lint.rules import RULE_DOCS, RULES, LintContext

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def lint_structure(
    structure: Structure, rules: Iterable[str] | None = None, data_version: int | None = None
) -> list[Diagnostic]:
    """Run lint rules (all by default) over every region.

    ``data_version`` overrides the schematic's own (``--mc-version``); rules use
    it where behaviour differs between versions.
    """
    selected = list(rules) if rules is not None else list(RULES)
    unknown = [r for r in selected if r not in RULES]
    if unknown:
        raise KeyError(f"unknown lint rule(s): {', '.join(unknown)}; known: {', '.join(RULES)}")
    out: list[Diagnostic] = []
    multi = len(structure.regions) > 1
    for region in structure.regions:
        ctx = LintContext(
            structure,
            region,
            PowerGraph.build(region),
            multi,
            data_version if data_version is not None else structure.data_version,
        )
        for rule_id in selected:
            out.extend(RULES[rule_id](ctx))
    return out


__all__ = ["RULES", "RULE_DOCS", "SEVERITY_ORDER", "LintContext", "apply_fix", "lint_structure"]
