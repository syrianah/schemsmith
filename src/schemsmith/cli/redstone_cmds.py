"""``lint`` and ``trace`` commands."""

from __future__ import annotations

import argparse
import json
from typing import Any

from schemsmith.diagnostics import has_errors
from schemsmith.formats import load_structure
from schemsmith.redstone.graph import PowerGraph
from schemsmith.redstone.lint import RULES, SEVERITY_ORDER, lint_structure
from schemsmith.redstone.sim import load_script, simulate
from schemsmith.registry import load_registry


def register(sub: Any) -> None:
    """Add ``lint`` and ``trace``."""
    p = sub.add_parser(
        "lint",
        help="find redstone and block placement mistakes (QC, panes on curves, ...)",
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
    register_simulate(sub)


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


def register_simulate(sub: Any) -> None:
    """Add ``simulate``."""
    p = sub.add_parser(
        "simulate",
        help="run an action script tick by tick and show what happens",
        description="Exit code: 0 = all expectations passed, 1 = an expectation failed.",
    )
    p.add_argument("file")
    p.add_argument("--script", required=True, help="YAML/JSON action script")
    p.add_argument("--ticks", type=int, help="override the script's tick count")
    p.add_argument("--max-timeline", type=int, default=60, help="timeline lines to print")
    p.add_argument("--format", choices=["text", "json"], default="text", dest="output")
    p.set_defaults(handler=cmd_simulate)


def cmd_simulate(args: argparse.Namespace) -> int:
    """Simulate a schematic with an action script."""
    script = load_script(args.script)
    if args.ticks is not None:
        script.ticks = args.ticks
    result = simulate(load_structure(args.file), script)
    if args.output == "json":
        print(json.dumps(result.to_dict(max_timeline=args.max_timeline), indent=2))
        return 0 if result.passed else 1
    print(
        f"{script.name}: {result.ticks} game ticks ({result.ticks / 20:.1f} s) simulated in "
        f"{result.elapsed_s * 1000:.0f} ms, {result.updates} updates, "
        f"confidence {result.confidence}"
    )
    if result.settle_ticks:
        print(f"note: saved states needed {result.settle_ticks} gt to settle before tick 0")
    print("events:")
    for e in result.events:
        detail = f" {e.detail}" if e.detail else ""
        print(f"  {e.tick:6d} gt  {e.kind:12s} ({e.pos[0]},{e.pos[1]},{e.pos[2]}){detail}")
    if result.timeline:
        print("timeline (watched blocks):")
        for t in result.timeline[: args.max_timeline]:
            print(f"  {t.tick:6d} gt  {t.label}: {t.value}")
        if len(result.timeline) > args.max_timeline:
            print(f"  ... {len(result.timeline) - args.max_timeline} more (--max-timeline)")
    if result.checks:
        print("expectations:")
        for c in result.checks:
            print(f"  [{'PASS' if c.passed else 'FAIL'}] {c.description} (actual: {c.actual})")
    print("simplifications: " + "; ".join(result.notes))
    return 0 if result.passed else 1
