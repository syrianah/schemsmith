"""``lint`` and ``trace`` commands."""

from __future__ import annotations

import argparse
import json
from typing import Any

from schemsmith.diagnostics import has_errors
from schemsmith.formats import load_structure
from schemsmith.redstone.graph import PowerGraph
from schemsmith.redstone.lint import RULES, SEVERITY_ORDER, lint_structure
from schemsmith.registry import load_registry


def register(sub: Any) -> None:
    """Add ``lint`` and ``trace``."""
    p = sub.add_parser(
        "lint",
        help="find redstone mistakes (quasi-connectivity, locked repeaters, ...)",
        description="Exit code: 0 = no errors, 1 = errors found, 2 = could not run. "
        f"Rules: {', '.join(RULES)}.",
    )
    p.add_argument("file")
    p.add_argument("--rule", action="append", choices=list(RULES), help="run only this rule")
    p.add_argument("--format", choices=["text", "json"], default="text", dest="output")
    p.add_argument("--mc-version", help="target Minecraft version (default: the file's)")
    p.set_defaults(handler=cmd_lint)

    p = sub.add_parser("trace", help="show what powers a block and what it powers")
    p.add_argument("file")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)
    p.add_argument("z", type=int)
    p.add_argument("--region", help="region name (default: the first region)")
    p.add_argument("--format", choices=["text", "json"], default="text", dest="output")
    p.set_defaults(handler=cmd_trace)


def cmd_lint(args: argparse.Namespace) -> int:
    """Lint a schematic; exit 1 when an error-level diagnostic is found."""
    s = load_structure(args.file)
    dv = load_registry(args.mc_version).data_version if args.mc_version else None
    diags = lint_structure(s, args.rule, dv)
    diags.sort(key=lambda d: (SEVERITY_ORDER[d.severity.value], d.rule_id, d.pos or (0, 0, 0)))
    if args.output == "json":
        print(
            json.dumps({"file": args.file, "diagnostics": [d.to_dict() for d in diags]}, indent=2)
        )
    else:
        for d in diags:
            print(d.format())
        counts = {k: sum(d.severity.value == k for d in diags) for k in SEVERITY_ORDER}
        print(
            f"{len(diags)} finding(s): {counts['error']} error(s), {counts['warning']} "
            f"warning(s), {counts['info']} info"
        )
    return 1 if has_errors(diags) else 0


def cmd_trace(args: argparse.Namespace) -> int:
    """Print the sources and sinks of one position."""
    s = load_structure(args.file)
    region = s.region(args.region) if args.region else s.regions[0]
    pos = (args.x, args.y, args.z)
    if not region.contains(*pos):
        raise ValueError(f"position {pos} is outside region of size {region.dims}")
    t = PowerGraph.build(region).trace(pos)
    if args.output == "json":
        print(json.dumps(t.to_dict(), indent=2))
    else:
        print(t.format())
    return 0
