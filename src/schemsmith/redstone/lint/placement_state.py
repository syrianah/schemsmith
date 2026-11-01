"""More block placement rules (issue #26): states the game recomputes from neighbours.

Every rule here is decided by blocks inside the schematic, the way the game does it:

* ``stairs-shape``: ``StairBlock.getStairsShape`` (inner/outer corners);
* ``wall-shape``: ``WallBlock`` side heights (``low``/``tall``) and the post (``up``);
* ``shelf-side-chain``: shelves only chain while powered, with powered shelves of the
  same facing beside them;
* ``leaf-decay``: ``LeavesBlock`` ``distance`` to the nearest log through leaves;
* ``scaffolding-state``: ``ScaffoldingBlock.getDistance`` and ``bottom``;
* ``fluid-flow``: fluid next to air flows (info: often intentional);
* ``plant-soil``: plants on the wrong block (hand-written table).

As in :mod:`~schemsmith.redstone.lint.placement`, positions outside the region are
unknown: a rule that would need one skips the block, except where noted (leaves
and scaffolding treat the outside as air/ground, see the rule docs).
"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Callable, Iterator

from schemsmith.core import BlockState
from schemsmith.diagnostics import Diagnostic, Severity
from schemsmith.redstone.graph.directions import HORIZONTAL, Dir, Vec3, step
from schemsmith.redstone.lint.placement import (
    _air,
    _inside,
    _set,
    _sturdy,
    _xyz,
    connects,
    is_wall,
)
from schemsmith.redstone.lint.rules import LintContext, rule

Getter = Callable[[Vec3], BlockState | None]
"""Block at a position, or None when it is outside the schematic."""

_CCW = {Dir.NORTH: Dir.WEST, Dir.WEST: Dir.SOUTH, Dir.SOUTH: Dir.EAST, Dir.EAST: Dir.NORTH}


def _getter(ctx: LintContext) -> Getter:
    g = ctx.graph
    return lambda q: g.state(q) if _inside(ctx, q) else None


# stairs ------------------------------------------------------------------------


def is_stairs(s: BlockState | None) -> bool:
    """Any stairs block."""
    return s is not None and s.name.endswith("_stairs")


def stair_shape(get: Getter, p: Vec3, s: BlockState) -> str | None:
    """``StairBlock.getStairsShape``; None when a needed neighbour is outside the schematic."""
    facing = s.get("facing")
    half = s.get("half")
    if facing is None:
        return None
    d = Dir.from_key(facing)
    front = get(step(p, d))
    back = get(step(p, d.opposite))
    if front is None or back is None:
        return None

    def can_take(face: Dir) -> bool | None:
        b = get(step(p, face))
        if b is None:
            return None
        return not is_stairs(b) or b.get("facing") != facing or b.get("half") != half

    if is_stairs(front) and front.get("half") == half and front.get("facing"):
        d1 = Dir.from_key(front["facing"])
        if (d1 in (Dir.EAST, Dir.WEST)) != (d in (Dir.EAST, Dir.WEST)):
            ok = can_take(d1.opposite)
            if ok is None:
                return None
            if ok:
                return "outer_left" if d1 == _CCW[d] else "outer_right"
    if is_stairs(back) and back.get("half") == half and back.get("facing"):
        d2 = Dir.from_key(back["facing"])
        if (d2 in (Dir.EAST, Dir.WEST)) != (d in (Dir.EAST, Dir.WEST)):
            ok = can_take(d2)
            if ok is None:
                return None
            if ok:
                return "inner_left" if d2 == _CCW[d] else "inner_right"
    return "straight"


@rule(
    "stairs-shape",
    "Stairs whose saved shape (straight/inner/outer corner) differs from what the game "
    "computes from the neighbouring stairs",
)
def stairs_shape(ctx: LintContext) -> Iterator[Diagnostic]:
    get = _getter(ctx)
    for p, s in sorted(ctx.graph.positions()):
        if not is_stairs(s):
            continue
        want = stair_shape(get, p, s)
        have = s.get("shape", "straight")
        if want is None or want == have:
            continue
        new = s.with_properties(shape=want)
        yield ctx.diag(
            "stairs-shape",
            Severity.WARNING,
            p,
            f"{ctx.name(p)} is saved as shape={have}, but its neighbouring stairs make it "
            f"{want}; the game changes it when the stairs or a neighbour update",
            f"save it as shape={want}",
            [_set(p, new)],
            f"set shape={want}",
        )


# walls ---------------------------------------------------------------------------

_POST_OVERRIDE = re.compile(r"(?<!wall_)torch$|(?<!hanging)_sign$|_banner$|_pressure_plate$")
"""``#minecraft:wall_post_override``: blocks that force a post on the wall below."""


def _covers_side(above: BlockState, d: Dir) -> bool | None:
    """Does the block above cover the wall's side ``d`` (``WallBlock.isCovered``)?"""
    if is_wall(above):
        return above.get(d.key) in ("low", "tall")
    sturdy = _sturdy(above)
    if sturdy is None:
        return None
    return sturdy


def wall_state(get: Getter, p: Vec3, s: BlockState) -> BlockState | None:
    """The state ``WallBlock`` computes (sides none/low/tall and ``up``), or None if unknown."""
    above = get(step(p, Dir.UP))
    if above is None:
        return None
    sides: dict[str, str] = {}
    for d in HORIZONTAL:
        n = get(step(p, d))
        if n is None:
            return None
        on = connects(s, n, d)
        if on is None:
            return None
        if not on:
            sides[d.key] = "none"
            continue
        covered = _covers_side(above, d)
        if covered is None:
            return None
        sides[d.key] = "tall" if covered else "low"
    if is_wall(above) and above.get("up") == "true":
        up = True
    else:
        none = {k: v == "none" for k, v in sides.items()}
        if all(none.values()) or none["north"] != none["south"] or none["west"] != none["east"]:
            up = True
        elif (sides["north"] == "tall" and sides["south"] == "tall") or (
            sides["east"] == "tall" and sides["west"] == "tall"
        ):
            up = False
        else:
            covered_post = _sturdy(above)
            if covered_post is None:
                return None
            up = bool(_POST_OVERRIDE.search(above.name)) or covered_post
    return s.with_properties(**sides, up="true" if up else "false")


@rule(
    "wall-shape",
    "Walls whose saved side heights (low/tall) or post (up) differ from what the game "
    "computes from the neighbours and the block above",
)
def wall_shape(ctx: LintContext) -> Iterator[Diagnostic]:
    get = _getter(ctx)
    for p, s in sorted(ctx.graph.positions()):
        if not is_wall(s):
            continue
        want = wall_state(get, p, s)
        if want is None:
            continue
        diffs = []
        for d in HORIZONTAL:
            have, need = s.get(d.key, "none"), want[d.key]
            # connected vs not is the connection-state rule; here only the height
            if have != need and "none" not in (have, need):
                diffs.append(f"{d.key}={need}")
        if s.get("up", "true") != want["up"]:
            diffs.append(f"up={want['up']}")
        if not diffs:
            continue
        new = s.with_properties(
            **{d.key: want[d.key] for d in HORIZONTAL if s.get(d.key, "none") != "none"},
            up=want["up"],
        )
        yield ctx.diag(
            "wall-shape",
            Severity.WARNING,
            p,
            f"{ctx.name(p)}: the game computes {', '.join(diffs)} from the neighbours and the "
            "block above (tall sides under a full block, a post where the wall turns or ends)",
            f"save it as {new}",
            [_set(p, new)],
            "set the wall shape the game will compute",
        )


# shelves -------------------------------------------------------------------------


def _is_shelf(s: BlockState | None) -> bool:
    return s is not None and s.name.endswith("_shelf") and s.get("side_chain") is not None


@rule(
    "shelf-side-chain",
    "Shelves whose side_chain does not fit their neighbours: unpowered shelves never chain, "
    "and a chain part needs powered shelves of the same facing beside it",
)
def shelf_side_chain(ctx: LintContext) -> Iterator[Diagnostic]:
    get = _getter(ctx)
    for p, s in sorted(ctx.graph.positions()):
        if not _is_shelf(s):
            continue
        part = s["side_chain"]
        if part == "unconnected":
            continue
        reason = None
        if s.get("powered") != "true":
            reason = "it is not powered, and only powered shelves chain"
        else:
            facing = Dir.from_key(s.get("facing", "north") or "north")
            row = (facing.rotate_cw(), facing.rotate_cw().opposite)
            linked = []
            unknown = False
            for d in row:
                n = get(step(p, d))
                if n is None:
                    unknown = True
                elif (
                    _is_shelf(n)
                    and n.get("facing") == s.get("facing")
                    and n.get("powered") == "true"
                    and n.get("side_chain") != "unconnected"
                ):
                    linked.append(d)
            need = 2 if part == "center" else 1
            if len(linked) < need and not unknown:
                reason = (
                    f"side_chain={part} needs {need} chained, powered shelf(s) with the same "
                    f"facing beside it, found {len(linked)}"
                )
        if reason is None:
            continue
        new = s.with_properties(side_chain="unconnected")
        yield ctx.diag(
            "shelf-side-chain",
            Severity.WARNING,
            p,
            f"{ctx.name(p)} is saved as side_chain={part}, but {reason}",
            "save it as side_chain=unconnected (the game chains powered shelves itself)",
            [_set(p, new)],
            "set side_chain=unconnected",
        )


# leaves --------------------------------------------------------------------------

_NOT_LOGS = re.compile(r"(mushroom|pumpkin|melon|dripleaf)_stem$|^minecraft:attached_")
_LOGS = re.compile(r"_(log|wood|stem|hyphae)$")
LEAF_MAX = 7


def is_log(s: BlockState) -> bool:
    """``#minecraft:logs`` (logs, wood, stripped variants, nether stems and hyphae)."""
    return bool(_LOGS.search(s.name)) and not _NOT_LOGS.search(s.name)


def is_leaves(s: BlockState) -> bool:
    """Any leaves block with a ``distance``."""
    return s.name.endswith("_leaves") and s.get("distance") is not None


def leaf_distances(ctx: LintContext) -> dict[Vec3, int]:
    """Distance of every leaves block to the nearest log through leaves (max 7)."""
    states = dict(ctx.graph.positions())
    dist: dict[Vec3, int] = {}
    queue: deque[Vec3] = deque()
    for p, s in states.items():
        if is_log(s):
            dist[p] = 0
            queue.append(p)
    while queue:
        p = queue.popleft()
        if dist[p] >= LEAF_MAX - 1:
            continue
        for d in Dir:
            q = step(p, d)
            if q not in dist and q in states and is_leaves(states[q]):
                dist[q] = dist[p] + 1
                queue.append(q)
    return {p: dist.get(p, LEAF_MAX) for p, s in states.items() if is_leaves(s)}


@rule(
    "leaf-decay",
    "Leaves with persistent=false that decay: no log within 6 blocks through leaves, or a "
    "saved distance=7 (decays on the next random tick); other wrong distances are info",
)
def leaf_decay(ctx: LintContext) -> Iterator[Diagnostic]:
    for p, want in sorted(leaf_distances(ctx).items()):
        s = ctx.graph.state(p)
        if s.get("persistent") == "true":
            continue
        have = int(s.get("distance", "7") or 7)
        if want >= LEAF_MAX:
            new = s.with_properties(persistent="true")
            yield ctx.diag(
                "leaf-decay",
                Severity.WARNING,
                p,
                f"{ctx.name(p)} has no log within 6 blocks (through leaves) in the schematic, "
                "so it decays; intentional only if it should vanish",
                "make it persistent (persistent=true, like player-placed leaves) or add a log",
                [_set(p, new)],
                "set persistent=true",
            )
        elif have != want:
            new = s.with_properties(distance=str(want))
            severe = have >= LEAF_MAX
            yield ctx.diag(
                "leaf-decay",
                Severity.WARNING if severe else Severity.INFO,
                p,
                f"{ctx.name(p)} is saved with distance={have}, the nearest log is {want} away"
                + ("; distance=7 leaves decay on the next random tick" if severe else ""),
                f"save it as distance={want}",
                [_set(p, new)],
                f"set distance={want}",
            )


# scaffolding ---------------------------------------------------------------------

SCAFFOLD = "minecraft:scaffolding"
SCAFFOLD_MAX = 7


def scaffolding_distances(ctx: LintContext) -> dict[Vec3, int | None]:
    """``ScaffoldingBlock.getDistance`` for every scaffolding block (None = unknown).

    A scaffold on the bottom layer stands on the ground (distance 0)."""
    states = dict(ctx.graph.positions())
    scaffolds = [p for p, s in states.items() if s.name == SCAFFOLD]
    dist: dict[Vec3, int] = {}
    unknown: set[Vec3] = set()
    dq: deque[Vec3] = deque()
    for p in scaffolds:
        below = step(p, Dir.DOWN)
        if not _inside(ctx, below):
            dist[p] = 0
            dq.append(p)
            continue
        b = states.get(below)
        if b is not None and b.name == SCAFFOLD:
            continue
        sturdy = _sturdy(b) if b is not None else False
        if sturdy is None:
            unknown.add(p)
        elif sturdy:
            dist[p] = 0
            dq.append(p)
    # 0-1 BFS: straight up costs 0, sideways costs 1
    while dq:
        p = dq.popleft()
        up = step(p, Dir.UP)
        if states.get(up, BlockState("minecraft:air")).name == SCAFFOLD and (
            up not in dist or dist[up] > dist[p]
        ):
            dist[up] = dist[p]
            dq.appendleft(up)
        for d in HORIZONTAL:
            q = step(p, d)
            if (
                states.get(q, BlockState("minecraft:air")).name == SCAFFOLD
                and dist[p] + 1 < dist.get(q, SCAFFOLD_MAX)
                and q not in unknown
            ):
                dist[q] = dist[p] + 1
                dq.append(q)
    return {
        p: (None if p in unknown and p not in dist else dist.get(p, SCAFFOLD_MAX))
        for p in scaffolds
    }


@rule(
    "scaffolding-state",
    "Scaffolding that falls (distance 7: more than 6 blocks sideways from a supported "
    "column), or whose saved distance/bottom differ from what the game computes",
)
def scaffolding_state(ctx: LintContext) -> Iterator[Diagnostic]:
    g = ctx.graph
    for p, want in sorted(scaffolding_distances(ctx).items()):
        if want is None:
            continue
        s = g.state(p)
        if want >= SCAFFOLD_MAX:
            yield ctx.diag(
                "scaffolding-state",
                Severity.WARNING,
                p,
                f"{ctx.name(p)} is more than 6 blocks sideways from a supported scaffolding "
                "column, so it falls",
                "add a scaffolding column down to a solid block within 6 blocks",
            )
            continue
        below = step(p, Dir.DOWN)
        on_scaffold = _inside(ctx, below) and g.state(below).name == SCAFFOLD
        bottom = want > 0 and not on_scaffold
        new = s.with_properties(distance=str(want), bottom="true" if bottom else "false")
        if new == s:
            continue
        yield ctx.diag(
            "scaffolding-state",
            Severity.INFO,
            p,
            f"{ctx.name(p)} is saved as distance={s.get('distance')}, bottom={s.get('bottom')}; "
            f"the game computes distance={want}, bottom={str(bottom).lower()}",
            f"save it as {new}",
            [_set(p, new)],
            "set the scaffolding state the game will compute",
        )


# fluid-flow ----------------------------------------------------------------------

_FLOWING = ("minecraft:water", "minecraft:lava")


@rule(
    "fluid-flow",
    "Water or lava next to air (sideways or below) inside the schematic: it flows out once "
    "placed (info: fountains and waterfalls do this on purpose)",
)
def fluid_flow(ctx: LintContext) -> Iterator[Diagnostic]:
    g = ctx.graph
    for p, s in sorted(g.positions()):
        if s.name not in _FLOWING:
            continue
        open_sides = [
            q
            for d in (*HORIZONTAL, Dir.DOWN)
            if _inside(ctx, q := step(p, d)) and g.state(q).is_air
        ]
        if not open_sides:
            continue
        kind = "source" if s.get("level", "0") == "0" else "flowing"
        yield ctx.diag(
            "fluid-flow",
            Severity.INFO,
            p,
            f"{s.short_name} {kind} at {_xyz(p)} is next to air at "
            f"{', '.join(_xyz(q) for q in open_sides)} and will flow there; fine for a "
            "fountain or waterfall",
            "close the gaps with blocks (or glass) if the fluid should stay put",
        )


# plant-soil ----------------------------------------------------------------------

DIRT = frozenset(
    "minecraft:" + n
    for n in [
        "dirt",
        "grass_block",
        "podzol",
        "coarse_dirt",
        "rooted_dirt",
        "mycelium",
        "moss_block",
        "pale_moss_block",
        "mud",
        "muddy_mangrove_roots",
    ]
)
"""``#minecraft:dirt``."""
SAND = frozenset({"minecraft:sand", "minecraft:red_sand", "minecraft:suspicious_sand"})
_FARMLAND = frozenset({"minecraft:farmland"})
_SMALL_FLOWERS = frozenset(
    "minecraft:" + n
    for n in [
        "dandelion",
        "poppy",
        "blue_orchid",
        "allium",
        "azure_bluet",
        "red_tulip",
        "orange_tulip",
        "white_tulip",
        "pink_tulip",
        "oxeye_daisy",
        "cornflower",
        "lily_of_the_valley",
        "torchflower",
        "open_eyeblossom",
        "closed_eyeblossom",
        "short_grass",
        "fern",
        "sunflower",
        "lilac",
        "rose_bush",
        "peony",
        "tall_grass",
        "large_fern",
        "pink_petals",
        "wildflowers",
    ]
)
_CROPS = frozenset(
    "minecraft:" + n
    for n in [
        "wheat",
        "carrots",
        "potatoes",
        "beetroots",
        "torchflower_crop",
        "pitcher_crop",
        "melon_stem",
        "pumpkin_stem",
        "attached_melon_stem",
        "attached_pumpkin_stem",
    ]
)
_MUSHROOM_GROW = frozenset(
    {
        "minecraft:mycelium",
        "minecraft:podzol",
        "minecraft:crimson_nylium",
        "minecraft:warped_nylium",
    }
)
_BAMBOO_SOIL = DIRT | SAND | {"minecraft:gravel", "minecraft:suspicious_gravel"}


def _soil(s: BlockState) -> tuple[frozenset[str] | None, str, str] | None:
    """``(allowed blocks below or None for 'sturdy top', what to say, fix block)``."""
    n = s.name
    if s.get("half") == "upper":
        return None
    if n == "minecraft:sugar_cane":
        return (
            DIRT | SAND | {n},
            "dirt, grass, sand or sugar cane (next to water)",
            "minecraft:sand",
        )
    if n == "minecraft:cactus":
        return SAND | {n}, "sand, red sand or cactus", "minecraft:sand"
    if n == "minecraft:nether_wart":
        return frozenset({"minecraft:soul_sand"}), "soul sand", "minecraft:soul_sand"
    if n in _CROPS:
        return _FARMLAND, "farmland", "minecraft:farmland[moisture=7]"
    if n.endswith("_sapling") and n != "minecraft:bamboo_sapling":
        return DIRT | _FARMLAND, "dirt, grass, moss, mud or farmland", "minecraft:dirt"
    if n == "minecraft:wither_rose":
        allowed = DIRT | _FARMLAND | {"minecraft:netherrack", "minecraft:soul_sand"}
        return (
            allowed | {"minecraft:soul_soil"},
            "dirt, netherrack or soul sand/soil",
            "minecraft:dirt",
        )
    if n in _SMALL_FLOWERS:
        return (
            DIRT | _FARMLAND,
            "dirt, grass, moss, mud or farmland",
            "minecraft:grass_block[snowy=false]",
        )
    if n in ("minecraft:bamboo", "minecraft:bamboo_sapling"):
        allowed = _BAMBOO_SOIL | {"minecraft:bamboo", "minecraft:bamboo_sapling"}
        return allowed, "dirt, sand, gravel or bamboo", "minecraft:dirt"
    if n in ("minecraft:kelp", "minecraft:kelp_plant"):
        return None, "a solid block (not magma) or kelp", "minecraft:sand"
    if n in ("minecraft:seagrass", "minecraft:tall_seagrass"):
        return None, "a solid block (not magma)", "minecraft:sand"
    if n in ("minecraft:brown_mushroom", "minecraft:red_mushroom"):
        return None, "mycelium, podzol, nylium, or a solid block in the dark", "minecraft:mycelium"
    return None


def _soil_ok(s: BlockState, below: BlockState, allowed: frozenset[str] | None) -> bool | None:
    if allowed is not None:
        return below.name in allowed
    n = s.name
    if n in ("minecraft:kelp", "minecraft:kelp_plant") and below.name in (
        "minecraft:kelp",
        "minecraft:kelp_plant",
    ):
        return True
    if n in ("minecraft:brown_mushroom", "minecraft:red_mushroom") and below.name in _MUSHROOM_GROW:
        return True
    if below.name == "minecraft:magma_block":
        return False
    return _sturdy(below)


def _water_next_to(get: Getter, soil: Vec3) -> bool | None:
    unknown = False
    for d in HORIZONTAL:
        n = get(step(soil, d))
        if n is None:
            unknown = True
            continue
        if n.name in ("minecraft:water", "minecraft:frosted_ice") or n.get("waterlogged") == "true":
            return True
    return None if unknown else False


@rule(
    "plant-soil",
    "Plants on a block they cannot grow on (sugar cane, cactus, nether wart, mushrooms, "
    "crops, saplings, flowers, bamboo, kelp, seagrass), sugar cane without water beside its "
    "soil, and cactus touching a solid block",
)
def plant_soil(ctx: LintContext) -> Iterator[Diagnostic]:
    get = _getter(ctx)
    for p, s in sorted(ctx.graph.positions()):
        rule_info = _soil(s)
        if rule_info is None:
            continue
        allowed, needed, fix_block = rule_info
        below_pos = step(p, Dir.DOWN)
        below = get(below_pos)
        if below is None or (
            _air(below) and s.name not in ("minecraft:kelp", "minecraft:seagrass")
        ):
            continue  # outside the schematic, or on air (needs-support / gravity)
        ok = _soil_ok(s, below, allowed)
        if ok is False:
            yield ctx.diag(
                "plant-soil",
                Severity.WARNING,
                p,
                f"{ctx.name(p)} stands on {below.short_name}; it needs {needed} and breaks "
                "when updated",
                f"put {fix_block.removeprefix('minecraft:').split('[')[0]} under it at "
                f"{_xyz(below_pos)}",
                [_set(below_pos, fix_block)],
                f"put {fix_block.split('[')[0]} under the plant",
            )
            continue
        if ok and s.name == "minecraft:sugar_cane" and below.name != s.name:
            water = _water_next_to(get, below_pos)
            if water is False:
                yield ctx.diag(
                    "plant-soil",
                    Severity.WARNING,
                    p,
                    f"{ctx.name(p)}: no water next to its soil at {_xyz(below_pos)}; sugar cane "
                    "breaks without it",
                    "put water (or a waterlogged block) beside the soil block",
                )
        if s.name == "minecraft:cactus":
            touching = [
                q
                for d in HORIZONTAL
                if (n := get(q := step(p, d))) is not None
                and (_sturdy(n) is True or n.name == "minecraft:lava")
            ]
            if touching:
                yield ctx.diag(
                    "plant-soil",
                    Severity.WARNING,
                    p,
                    f"{ctx.name(p)} touches a solid block or lava at "
                    f"{', '.join(_xyz(q) for q in touching)}; cactus breaks there",
                    "leave the four sides of a cactus free (air or non-solid blocks)",
                )


PLACEMENT_STATE_RULES = (
    "stairs-shape",
    "wall-shape",
    "shelf-side-chain",
    "leaf-decay",
    "scaffolding-state",
    "fluid-flow",
    "plant-soil",
)
