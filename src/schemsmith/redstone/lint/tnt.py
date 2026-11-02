"""``place-ignites-tnt``: TNT that gets lit right after ``/place template``.

Lab fact (owner, 26.3): ``/place template`` does no block updates, yet TNT that
sits next to an observer or a powered component in the template was lit right
after placing (a TNT duper). The owner's farm had to be placed without its duper
TNT and observer, which were then set by hand.

The rule warns for TNT with, on one of its six sides, an observer (any facing,
any state), a component that powers it and is on in the saved state (a powered
lever, button, plate, repeater, comparator or observer, a lit redstone torch,
wire with ``power`` > 0, a redstone block, a detector with ``power`` > 0), or a
block that such a component powers.
"""

from __future__ import annotations

from collections.abc import Iterator

from schemsmith.core import BlockState
from schemsmith.diagnostics import Diagnostic, Severity
from schemsmith.redstone.graph import components as C
from schemsmith.redstone.graph.directions import ALL, Vec3, step
from schemsmith.redstone.lint.rules import LintContext, rule

RULE_ID = "place-ignites-tnt"
HINT = "place without these blocks, then set them last"


def saved_on(s: BlockState) -> bool:
    """True when the saved state says this component is giving power."""
    if s.name == "minecraft:redstone_block":
        return True
    props = dict(s.properties)
    if C.is_torch(s):
        return props.get("lit", "true") == "true"
    if props.get("powered") == "true":
        return True
    power = props.get("power")
    return power is not None and power.isdigit() and int(power) > 0


def _xyz(p: Vec3) -> str:
    return f"({p[0]},{p[1]},{p[2]})"


def triggers(ctx: LintContext, p: Vec3) -> list[str]:
    """Why the TNT at ``p`` may be lit when placed (labels of the blocks)."""
    g = ctx.graph
    out: list[str] = []
    for d in ALL:
        n = step(p, d)
        if ctx.region.contains(*n) and C.is_observer(g.state(n)):
            out.append(f"observer {_xyz(n)}")
    for e in g.inputs(p):
        if e.dst_role != "c" or not ctx.region.contains(*e.src):
            continue
        src = g.state(e.src)
        if e.src_role == "c":
            if saved_on(src) and not C.is_observer(src):
                out.append(f"powered {src.short_name} {_xyz(e.src)}")
        elif any(
            i.dst_role == "b" and i.src_role == "c" and saved_on(g.state(i.src))
            for i in g.inputs(e.src)
        ):
            out.append(f"powered {src.short_name} {_xyz(e.src)}")
    return list(dict.fromkeys(out))


@rule(
    RULE_ID,
    "TNT next to an observer, a powered component or a powered block: /place template "
    "lights it right after placing (26.3)",
)
def place_ignites_tnt(ctx: LintContext) -> Iterator[Diagnostic]:
    g = ctx.graph
    for p, s in sorted(g.positions()):
        if s.name != "minecraft:tnt":
            continue
        why = triggers(ctx, p)
        if not why:
            continue
        others = ", ".join(why)
        yield ctx.diag(
            RULE_ID,
            Severity.WARNING,
            p,
            f"{ctx.name(p)} is next to {others}: TNT like this was lit right after "
            "/place template in 26.3 (a TNT duper), although the command does no block updates",
            f"{HINT}: TNT at {_xyz(p)}, then {others}",
        )


__all__ = ["HINT", "RULE_ID", "place_ignites_tnt", "saved_on", "triggers"]
