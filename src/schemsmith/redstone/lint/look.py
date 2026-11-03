"""Build-quality lint rule: holes in fence lines on round and stepped walls.

Fences on a voxel circle often touch only at a corner, which shows as a hole in the rail.
The rule was calibrated on a generated build, the same build fixed by hand, and two
hand-built references. Ledges and walls are left out: the hand-built references step them
diagonally on purpose. Contrast metrics for material noise are not shipped either: they
ranked a good hand-built silo below a bad generated one. Judge looks from real-texture
renders and by people.
"""

from __future__ import annotations

from collections.abc import Iterator

from schemsmith.diagnostics import Diagnostic, Severity
from schemsmith.redstone.graph.directions import Vec3
from schemsmith.redstone.lint.placement import _air, _xyz, is_fence
from schemsmith.redstone.lint.rules import LintContext, rule


@rule(
    "fence-gap",
    "Fences on one layer that continue diagonally and leave an open corner: a visible hole "
    "in the rail",
)
def fence_gap(ctx: LintContext) -> Iterator[Diagnostic]:
    g = ctx.graph
    for p, s in sorted(g.positions()):
        if not is_fence(s):
            continue
        x, y, z = p
        for dz in (-1, 1):
            q: Vec3 = (x + 1, y, z + dz)
            corners: tuple[Vec3, Vec3] = ((x + 1, y, z), (x, y, z + dz))
            if not all(ctx.region.contains(*c) for c in (q, *corners)):
                continue
            if not is_fence(g.state(q)):
                continue
            states = [g.state(c) for c in corners]
            if any(is_fence(c) for c in states):
                continue
            open_corners = [c for c, st in zip(corners, states, strict=True) if _air(st)]
            if not open_corners:
                continue
            yield ctx.diag(
                "fence-gap",
                Severity.WARNING,
                p,
                f"{ctx.name(p)} continues diagonally to {_xyz(q)} and leaves the corner "
                f"{_xyz(open_corners[0])} open: the rail has a hole there",
                f"put a fence at {_xyz(open_corners[0])}",
            )
