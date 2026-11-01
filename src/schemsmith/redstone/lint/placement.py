"""Block placement lint rules (issue #21).

Blocks that look or behave differently once placed in the game than in the
schematic preview: glass panes on curves, saved fence/pane/wall connections,
blocks that need support, gravity blocks, two-block blocks and chest pairs.

Positions outside the region are unknown (the world around the schematic), so a
rule never complains about a neighbour it cannot see: blocks on the bottom
layer are assumed to stand on the ground. "Air" here means air, water or lava
(nothing a torch or a button can attach to). Whether a neighbour gives a
*sturdy face* (fences and panes connect to it) uses the conductive heuristic
from :mod:`schemsmith.registry.categories` (issue #9) plus glass; neighbours we
cannot classify (stairs, slabs, trapdoors, ...) are skipped.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from schemsmith.core import BlockState
from schemsmith.diagnostics import Diagnostic, Severity
from schemsmith.redstone.graph.directions import HORIZONTAL, Dir, Vec3, step
from schemsmith.redstone.lint.rules import LintContext, rule
from schemsmith.registry.categories import is_conductive

_FLUIDS = frozenset({"minecraft:water", "minecraft:lava", "minecraft:bubble_column"})


def _p(pos: Vec3) -> list[int]:
    return [pos[0], pos[1], pos[2]]


def _xyz(pos: Vec3) -> str:
    return f"({pos[0]},{pos[1]},{pos[2]})"


def _inside(ctx: LintContext, pos: Vec3) -> bool:
    return ctx.region.contains(*pos)


def _air(state: BlockState) -> bool:
    return state.is_air or state.id in _FLUIDS


def _short(state_id: str) -> str:
    return state_id.removeprefix("minecraft:")


def _set(pos: Vec3, state: BlockState | str) -> dict[str, object]:
    return {"op": "set", "pos": _p(pos), "state": str(state)}


# families ----------------------------------------------------------------------


def is_pane(s: BlockState) -> bool:
    """Glass panes and bars (iron, copper): they connect to each other."""
    n = _short(s.id)
    return n.endswith("glass_pane") or n.endswith("_bars") or n == "iron_bars"


def is_fence(s: BlockState) -> bool:
    """Fences (not fence gates)."""
    return s.id.endswith("_fence")


def is_wall(s: BlockState) -> bool:
    """Walls (``cobblestone_wall``, ...), not wall torches or signs."""
    return s.id.endswith("_wall")


def is_gate(s: BlockState) -> bool:
    """Fence gates."""
    return s.id.endswith("_fence_gate")


def _wooden_fence(s: BlockState) -> bool:
    return s.id != "minecraft:nether_brick_fence"


_GLASS = re.compile(r"^minecraft:((\w+_)?stained_glass|glass|tinted_glass)$")
_NO_CONNECT = re.compile(
    r"(leaves|shulker_box)$|^minecraft:(barrier|pumpkin|carved_pumpkin|jack_o_lantern|melon)$"
)
_NOT_STURDY = re.compile(
    r"(torch|_carpet|_button|^minecraft:lever|rail|redstone_wire|_sign|_banner|_pressure_plate"
    r"|candle|^minecraft:(soul_|\w+_copper_|copper_)?lantern|chain|ladder|vine|_sapling"
    r"|^minecraft:(short_grass|fern|dandelion|poppy|tall_grass|large_fern))$"
)


def _sturdy(s: BlockState) -> bool | None:
    """Does ``s`` give a full face that fences, panes and walls attach to? None = unknown."""
    if _air(s) or _NO_CONNECT.search(s.id):
        return False
    if _GLASS.match(s.id) or is_conductive(s):
        return True
    if _NOT_STURDY.search(s.id):
        return False
    return None


def _gate_joins(gate: BlockState, d: Dir) -> bool:
    facing = gate.get("facing", "north") or "north"
    gate_axis_x = facing in ("east", "west")
    return gate_axis_x != (d in (Dir.EAST, Dir.WEST))


def connects(block: BlockState, neighbour: BlockState, d: Dir) -> bool | None:
    """Would the game connect ``block`` (fence/pane/wall) towards ``neighbour`` at ``d``?"""
    if is_pane(block):
        if is_pane(neighbour) or is_wall(neighbour):
            return True
        if is_fence(neighbour) or is_gate(neighbour):
            return False
        return _sturdy(neighbour)
    if is_fence(block):
        if is_fence(neighbour):
            return _wooden_fence(block) == _wooden_fence(neighbour)
        if is_gate(neighbour):
            return _gate_joins(neighbour, d)
        if is_pane(neighbour) or is_wall(neighbour):
            return False
        return _sturdy(neighbour)
    if is_wall(block):
        if is_wall(neighbour) or is_pane(neighbour):
            return True
        if is_gate(neighbour):
            return _gate_joins(neighbour, d)
        if is_fence(neighbour):
            return False
        return _sturdy(neighbour)
    return None


# pane-diagonal -------------------------------------------------------------------


def full_block_for_pane(s: BlockState) -> str | None:
    """``red_stained_glass_pane`` → ``minecraft:red_stained_glass``; None for bars."""
    if s.id.endswith("glass_pane"):
        return s.id.removesuffix("_pane")
    return None


def _bridges(ctx: LintContext, a: Vec3) -> bool:
    s = ctx.graph.state(a)
    return is_pane(s) or is_wall(s) or _sturdy(s) is True


@rule(
    "pane-diagonal",
    "Glass panes/bars whose wall runs diagonally (curves, 45° walls): panes only connect "
    "orthogonally, so the game shows thin posts and gaps",
)
def pane_diagonal(ctx: LintContext) -> Iterator[Diagnostic]:
    g = ctx.graph
    for p, s in sorted(g.positions()):
        if not is_pane(s):
            continue
        diagonal = []
        for dx, dz in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            q = (p[0] + dx, p[1], p[2] + dz)
            if not is_pane(g.state(q)):
                continue
            a, b = (p[0] + dx, p[1], p[2]), (p[0], p[1], p[2] + dz)
            if not _bridges(ctx, a) and not _bridges(ctx, b):
                diagonal.append(q)
        if not diagonal:
            continue
        full = full_block_for_pane(s)
        orth = sum(1 for d in HORIZONTAL if connects(s, g.state(step(p, d)), d))
        alt = f"use full {full} here" if full else "use a full block here"
        yield ctx.diag(
            "pane-diagonal",
            Severity.WARNING,
            p,
            f"{ctx.name(p)} continues diagonally to {', '.join(_xyz(q) for q in diagonal)} "
            f"with {orth} orthogonal connection(s): panes only connect orthogonally, so a "
            "curved or 45° wall shows thin posts and gaps in game",
            f"{alt}, or give every pane two orthogonal neighbours "
            "(a pane in one of the corner gaps)",
            [_set(p, full)] if full else None,
            f"replace with {full}" if full else None,
        )


# connection-state ----------------------------------------------------------------


def _saved(block: BlockState, d: Dir) -> bool:
    v = block.get(d.key)
    if is_wall(block):
        return v not in (None, "none")
    return v == "true"


def _value(block: BlockState, d: Dir, on: bool) -> str:
    if not is_wall(block):
        return "true" if on else "false"
    if not on:
        return "none"
    current = block.get(d.key)
    return current if current in ("low", "tall") else "low"


@rule(
    "connection-state",
    "Fences, panes, bars and walls whose saved north/east/south/west connections do not "
    "match their neighbours (the game recomputes them, so the build differs from the preview)",
)
def connection_state(ctx: LintContext) -> Iterator[Diagnostic]:
    g = ctx.graph
    for p, s in sorted(g.positions()):
        if not (is_pane(s) or is_fence(s) or is_wall(s)):
            continue
        wrong: list[tuple[Dir, bool]] = []
        for d in HORIZONTAL:
            q = step(p, d)
            if not _inside(ctx, q):
                continue
            want = connects(s, g.state(q), d)
            if want is not None and want != _saved(s, d):
                wrong.append((d, want))
        if not wrong:
            continue
        new = s.with_properties(
            **{d.key: _value(s, d, on) for d, on in wrong},
        )
        what = ", ".join(f"{d.key}={'connected' if on else 'not connected'}" for d, on in wrong)
        yield ctx.diag(
            "connection-state",
            Severity.WARNING,
            p,
            f"{ctx.name(p)}: saved connections differ from its neighbours ({what}); the game "
            "recomputes them when the block or a neighbour updates",
            f"save it as {new}",
            [_set(p, new)],
            "set the connections the game will compute",
        )


# needs-support -------------------------------------------------------------------

SOIL = frozenset(
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
        "farmland",
    ]
)
"""Blocks saplings, flowers and grass can be planted on."""
_FLOWERS = frozenset(
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
        "wither_rose",
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
    ]
)


def _is_plant(s: BlockState) -> bool:
    if s.get("half") == "upper":
        return False
    sapling = s.id.endswith("_sapling") and s.id != "minecraft:bamboo_sapling"
    return sapling or s.id in _FLOWERS


_FLOOR = re.compile(
    r"_carpet$|_pressure_plate$|rail$|^minecraft:(redstone_wire|repeater|comparator|snow|cake)$"
    r"|(^minecraft:|_)candle$|candle_cake$"
)
_LANTERN = re.compile(r"(^minecraft:|_)lantern$")
_WALL_FACING = re.compile(
    r"wall_torch$|_wall_sign$|_wall_banner$|^minecraft:(ladder|tripwire_hook)$"
)
_VINE_FACES: dict[str, tuple[Dir, ...]] = {"minecraft:vine": (*HORIZONTAL, Dir.UP)}
_MULTIFACE = frozenset({"minecraft:glow_lichen", "minecraft:sculk_vein", "minecraft:resin_clump"})


def support_of(s: BlockState) -> list[Dir] | None:
    """Directions one of which must hold a block for ``s`` to stay; None = no rule."""
    n = s.id
    if n.endswith("torch") and "wall_torch" not in n:
        return [Dir.DOWN]
    if _FLOOR.search(n) or _is_plant(s):
        return [Dir.DOWN]
    if n.endswith("_sign") and "wall" not in n and "hanging" not in n:
        return [Dir.DOWN]
    if n.endswith("_banner") and "wall" not in n:
        return [Dir.DOWN]
    if n.endswith("_hanging_sign") and "wall" not in n:
        return [Dir.UP]
    if n.endswith("_door") and s.get("half") == "lower":
        return [Dir.DOWN]
    if _LANTERN.search(n) and n not in ("minecraft:jack_o_lantern", "minecraft:sea_lantern"):
        return [Dir.UP] if s.get("hanging") == "true" else [Dir.DOWN]
    if n == "minecraft:pointed_dripstone":
        return [Dir.UP] if s.get("vertical_direction") == "down" else [Dir.DOWN]
    if _WALL_FACING.search(n) and s.get("facing"):
        return [Dir.from_key(s["facing"]).opposite]
    if (n.endswith("_button") or n == "minecraft:lever") and s.get("face"):
        face = s["face"]
        if face == "floor":
            return [Dir.DOWN]
        if face == "ceiling":
            return [Dir.UP]
        return [Dir.from_key(s.get("facing", "north") or "north").opposite]
    faces = _VINE_FACES.get(n)
    if faces is None and n in _MULTIFACE:
        faces = (*HORIZONTAL, Dir.UP, Dir.DOWN)
    if faces is not None:
        return [d for d in faces if s.get(d.key) == "true"]
    return None


def _where(d: Dir) -> str:
    return {Dir.DOWN: "below", Dir.UP: "above"}.get(d, f"to the {d.key}")


@rule(
    "needs-support",
    "Torches, lanterns, candles, carpets, plates, rails, buttons, levers, signs, banners, "
    "ladders, vines and plants placed on air (they pop off), and plants not on soil",
)
def needs_support(ctx: LintContext) -> Iterator[Diagnostic]:
    g = ctx.graph
    for p, s in sorted(g.positions()):
        dirs = support_of(s)
        if dirs is None:
            continue
        if s.id == "minecraft:vine" and g.state(step(p, Dir.UP)).id == "minecraft:vine":
            continue  # hangs from the vine above
        if not dirs:
            dirs = [Dir.UP]  # a vine with no faces at all
        seen = [step(p, d) for d in dirs]
        if any(not _inside(ctx, q) for q in seen):
            continue  # the support is outside the schematic: the world decides
        if all(_air(g.state(q)) for q in seen):
            where = " / ".join(f"{_where(d)} {_xyz(q)}" for d, q in zip(dirs, seen, strict=True))
            yield ctx.diag(
                "needs-support",
                Severity.WARNING,
                p,
                f"{ctx.name(p)} has only air {where}; it breaks (pops off) when placed or updated",
                f"put a solid block {where}, or move the {s.short_name}",
            )
            continue
        if _is_plant(s):
            below = g.state(step(p, Dir.DOWN))
            if below.id not in SOIL and not _air(below):
                yield ctx.diag(
                    "needs-support",
                    Severity.WARNING,
                    p,
                    f"{ctx.name(p)} stands on {below.short_name}, not on soil; the game will "
                    "not keep it there",
                    f"put dirt, grass_block or moss_block under it at {_xyz(step(p, Dir.DOWN))}",
                    [_set(step(p, Dir.DOWN), "minecraft:grass_block[snowy=false]")],
                    "put grass_block under the plant",
                )


# gravity-block -------------------------------------------------------------------

GRAVITY = re.compile(
    r"^minecraft:(sand|red_sand|gravel|suspicious_sand|suspicious_gravel|anvil|chipped_anvil"
    r"|damaged_anvil|dragon_egg|\w+_concrete_powder)$"
)


def solid_for_falling(s: BlockState) -> str | None:
    """A look-alike block that does not fall, or None."""
    if s.id.endswith("_concrete_powder"):
        return s.id.removesuffix("_powder")
    return {
        "minecraft:sand": "minecraft:sandstone",
        "minecraft:red_sand": "minecraft:red_sandstone",
    }.get(s.id)


@rule("gravity-block", "Sand, gravel, concrete powder, anvils and dragon eggs over air (they fall)")
def gravity_block(ctx: LintContext) -> Iterator[Diagnostic]:
    g = ctx.graph
    for p, s in sorted(g.positions()):
        if not GRAVITY.match(s.id):
            continue
        below = step(p, Dir.DOWN)
        if not _inside(ctx, below) or not _air(g.state(below)):
            continue
        alt = solid_for_falling(s)
        tip = f"use {alt}, or put a block under it" if alt else "put a block under it"
        yield ctx.diag(
            "gravity-block",
            Severity.WARNING,
            p,
            f"{ctx.name(p)} is over air at {_xyz(below)}; it falls when placed or updated",
            tip,
            [_set(p, alt)] if alt else None,
            f"replace with {alt}" if alt else None,
        )


# two-block-half ------------------------------------------------------------------


def _partner(p: Vec3, s: BlockState) -> tuple[Vec3, BlockState] | None:
    """Where the other half of a door/tall plant/bed must be, and what it must be."""
    half = s.get("half")
    if half in ("lower", "upper"):
        d = Dir.UP if half == "lower" else Dir.DOWN
        return step(p, d), s.with_properties(half="upper" if half == "lower" else "lower")
    part = s.get("part")
    if s.id.endswith("_bed") and part in ("foot", "head") and s.get("facing"):
        facing = Dir.from_key(s["facing"])
        d = facing if part == "foot" else facing.opposite
        return step(p, d), s.with_properties(part="head" if part == "foot" else "foot")
    return None


@rule(
    "two-block-half",
    "Doors, beds, tall plants and other two-block blocks with the other half missing",
)
def two_block_half(ctx: LintContext) -> Iterator[Diagnostic]:
    g = ctx.graph
    for p, s in sorted(g.positions()):
        found = _partner(p, s)
        if found is None:
            continue
        q, want = found
        if not _inside(ctx, q):
            continue
        have = g.state(q)
        if have.id == s.id and all(
            have.get(k) == want.get(k) for k in ("half", "part", "facing") if want.get(k)
        ):
            continue
        fix = [_set(q, want)] if have.is_air else None
        yield ctx.diag(
            "two-block-half",
            Severity.ERROR,
            p,
            f"{ctx.name(p)} is missing its other half at {_xyz(q)} "
            f"(found {have.short_name}); the game breaks a lone half",
            f"place {want} at {_xyz(q)}" if fix else f"free {_xyz(q)} for the other half",
            fix,
            f"add the other half at {_xyz(q)}",
        )


# chest-partner -------------------------------------------------------------------

_CHESTS = re.compile(r"^minecraft:(chest|trapped_chest|(\w+_)?copper_chest)$")


@rule("chest-partner", "Chests saved as the left/right half of a double chest with no partner")
def chest_partner(ctx: LintContext) -> Iterator[Diagnostic]:
    g = ctx.graph
    for p, s in sorted(g.positions()):
        kind = s.get("type")
        if not _CHESTS.match(s.id) or kind not in ("left", "right") or not s.get("facing"):
            continue
        facing = Dir.from_key(s["facing"])
        d = facing.rotate_cw() if kind == "left" else facing.rotate_cw().rotate_cw().rotate_cw()
        q = step(p, d)
        if not _inside(ctx, q):
            continue
        other = g.state(q)
        mate = "right" if kind == "left" else "left"
        if (
            _CHESTS.match(other.id)
            and other.get("type") == mate
            and other.get("facing") == s.get("facing")
        ):
            continue
        new = s.with_properties(type="single")
        yield ctx.diag(
            "chest-partner",
            Severity.WARNING,
            p,
            f"{ctx.name(p)} is saved as the {kind} half of a double chest, but {_xyz(q)} is "
            f"{other.short_name}; it shows as half a double chest until updated",
            "save it as type=single, or add the other half",
            [_set(p, new)],
            "make it a single chest",
        )


PLACEMENT_RULES = (
    "pane-diagonal",
    "connection-state",
    "needs-support",
    "gravity-block",
    "two-block-half",
    "chest-partner",
)
