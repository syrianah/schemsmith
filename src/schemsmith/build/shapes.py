"""Auto-shapes: recompute connection properties the way the game does on placement.

* redstone wire: from the power graph (``PowerGraph.wire_shapes``);
* fences, glass panes, iron bars: connect to the same family and to full blocks;
* walls: ``low`` connections, a post (``up=true``) unless it is a straight line;
* stairs: ``shape`` from the neighbouring stairs, like ``StairBlock.getStairsShape``.

Full-block detection uses the conductive heuristic (issue #9).
"""

from __future__ import annotations

from schemsmith.core import BlockState, Region
from schemsmith.redstone.graph import PowerGraph
from schemsmith.redstone.graph.directions import HORIZONTAL, Dir, Vec3, step
from schemsmith.registry.categories import is_conductive

_CCW = {Dir.NORTH: Dir.WEST, Dir.WEST: Dir.SOUTH, Dir.SOUTH: Dir.EAST, Dir.EAST: Dir.NORTH}


def _family(s: BlockState) -> str | None:
    n = s.name
    if n.endswith("_fence_gate"):
        return "gate"
    if n == "minecraft:nether_brick_fence":
        return "nether_fence"
    if n.endswith("_fence"):
        return "fence"
    if n.endswith("glass_pane") or n == "minecraft:iron_bars" or n.endswith("_bars"):
        return "pane"
    if n.endswith("_wall") and not n.endswith(
        ("_sign", "_banner", "_torch", "_head", "_skull", "_fan")
    ):
        return "wall"
    return None


def _full(s: BlockState) -> bool:
    return not s.is_air and is_conductive(s)


def _connects(fam: str, other: BlockState, side_from_other: Dir) -> bool:
    of = _family(other)
    if _full(other):
        return True
    if fam in ("fence", "nether_fence"):
        if of == fam:
            return True
        if of == "gate":
            f = other.get("facing")
            return f is not None and Dir.from_key(f) in (
                side_from_other.rotate_cw(),
                _CCW[side_from_other],
            )
        return False
    if fam == "pane":
        return of in ("pane", "wall")
    if fam == "wall":
        return of in ("wall", "pane", "gate")
    return False


def _stair_shape(region: Region, p: Vec3, s: BlockState) -> str:
    def get(q: Vec3) -> BlockState:
        return region.get_block(*q) if region.contains(*q) else BlockState("minecraft:air")

    def is_stairs(b: BlockState) -> bool:
        return b.name.endswith("_stairs")

    d = Dir.from_key(s.get("facing") or "north")
    half = s.get("half")

    def can_take(face: Dir) -> bool:
        b = get(step(p, face))
        return not is_stairs(b) or b.get("facing") != s.get("facing") or b.get("half") != half

    front = get(step(p, d))
    if is_stairs(front) and front.get("half") == half:
        d1 = Dir.from_key(front.get("facing") or "north")
        if (d1 in (Dir.EAST, Dir.WEST)) != (d in (Dir.EAST, Dir.WEST)) and can_take(d1.opposite):
            return "outer_left" if d1 == _CCW[d] else "outer_right"
    back = get(step(p, d.opposite))
    if is_stairs(back) and back.get("half") == half:
        d2 = Dir.from_key(back.get("facing") or "north")
        if (d2 in (Dir.EAST, Dir.WEST)) != (d in (Dir.EAST, Dir.WEST)) and can_take(d2):
            return "inner_left" if d2 == _CCW[d] else "inner_right"
    return "straight"


def update_shapes(region: Region) -> int:
    """Recompute connection properties in place; returns how many blocks changed."""
    changed = 0
    graph = PowerGraph.build(region)
    updates: dict[Vec3, BlockState] = {}
    for p, s in region.blocks():
        if p in graph.wire_shapes:
            updates[p] = graph.expected_wire_state(p)
            continue
        fam = _family(s)
        if fam in ("fence", "nether_fence", "pane", "wall"):
            sides: dict[str, str] = {}
            for d in HORIZONTAL:
                q = step(p, d)
                other = region.get_block(*q) if region.contains(*q) else BlockState("minecraft:air")
                ok = _connects(fam, other, d.opposite)
                if fam == "wall":
                    sides[d.key] = "low" if ok else "none"
                else:
                    sides[d.key] = "true" if ok else "false"
            if fam == "wall":
                c = {k for k, v in sides.items() if v != "none"}
                straight = c in ({"north", "south"}, {"east", "west"})
                sides["up"] = "false" if straight else "true"
            updates[p] = s.with_properties(**sides)
        elif s.name.endswith("_stairs"):
            updates[p] = s.with_properties(shape=_stair_shape(region, p, s))
    for p, new in updates.items():
        if region.get_block(*p) != new:
            region.set_block(*p, new)
            changed += 1
    return changed
