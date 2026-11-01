"""Which blocks a piston moves (issue #16).

A port of the rules in Java Edition's ``PistonStructureResolver`` and
``PistonBaseBlock.isPushable`` (as described on the Minecraft Wiki "Piston" page
and in ``.claude/skills/minecraft-redstone`` §6):

* at most :data:`PUSH_LIMIT` blocks move;
* immovable blocks (obsidian, bedrock, block entities, extended pistons, ...) stop
  the piston; fragile blocks (wire, torches, plants, ...) are destroyed;
* slime and honey blocks drag their neighbours, but not each other;
* push-only blocks (glazed terracotta) move when pushed, never when pulled, and
  never stick;
* a sticky piston pulls one block (plus whatever slime/honey drags along).

Which block reacts how is a hand-written table (the game stores it per block);
blocks we do not know are treated as normal, movable blocks.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from schemsmith.core import BlockState
from schemsmith.core.edits import slots_for
from schemsmith.redstone.graph.directions import ALL, Dir, Vec3, step

PUSH_LIMIT = 12

_FLUIDS = frozenset({"minecraft:water", "minecraft:lava", "minecraft:bubble_column"})
IMMOVABLE = frozenset(
    "minecraft:" + n
    for n in [
        "obsidian",
        "crying_obsidian",
        "respawn_anchor",
        "reinforced_deepslate",
        "bedrock",
        "barrier",
        "end_portal_frame",
        "end_portal",
        "end_gateway",
        "command_block",
        "chain_command_block",
        "repeating_command_block",
        "structure_block",
        "jigsaw",
        "light",
        "piston_head",
        "moving_piston",
        "grindstone",
        "beacon",
        "enchanting_table",
        "ender_chest",
        "jukebox",
        "lectern",
        "spawner",
        "trial_spawner",
        "vault",
        "conduit",
        "daylight_detector",
        "brewing_stand",
        "chiseled_bookshelf",
        "creaking_heart",
        "crafter",
        "end_crystal",
    ]
)
"""Never move (``PushReaction.BLOCK``, unbreakable, or a block entity)."""
_IMMOVABLE_PATTERNS = re.compile(r"(^minecraft:|_)(campfire|bed)$|_shelf$")

_DESTROY_EXACT = frozenset(
    "minecraft:" + n
    for n in [
        "redstone_wire",
        "repeater",
        "comparator",
        "lever",
        "tripwire",
        "tripwire_hook",
        "cobweb",
        "snow",
        "fire",
        "soul_fire",
        "ladder",
        "flower_pot",
        "dragon_egg",
        "turtle_egg",
        "sniffer_egg",
        "sea_pickle",
        "cake",
        "pointed_dripstone",
        "lily_pad",
        "frogspawn",
        "hanging_roots",
        "glow_lichen",
        "sculk_vein",
        "resin_clump",
        "big_dripleaf",
        "big_dripleaf_stem",
        "small_dripleaf",
        "spore_blossom",
        "azalea",
        "flowering_azalea",
        "pumpkin",
        "carved_pumpkin",
        "jack_o_lantern",
        "melon",
        "sugar_cane",
        "kelp",
        "kelp_plant",
        "cactus",
        "bamboo",
        "bamboo_sapling",
        "cocoa",
        "nether_wart",
        "sweet_berry_bush",
        "wheat",
        "carrots",
        "potatoes",
        "beetroots",
        "torchflower_crop",
        "pitcher_crop",
        "pumpkin_stem",
        "melon_stem",
        "attached_pumpkin_stem",
        "attached_melon_stem",
        "short_grass",
        "tall_grass",
        "fern",
        "large_fern",
        "dead_bush",
        "seagrass",
        "tall_seagrass",
        "vine",
        "weeping_vines",
        "weeping_vines_plant",
        "twisting_vines",
        "twisting_vines_plant",
        "cave_vines",
        "cave_vines_plant",
        "chorus_plant",
        "chorus_flower",
        "decorated_pot",
        "bell",
        "nether_portal",
        "scaffolding",
    ]
)
_DESTROY_PATTERNS = re.compile(
    r"(torch|_button|_pressure_plate|_door|_sapling|_carpet|_sign|_banner|_head|_skull"
    r"|candle|lantern|_coral|_coral_fan|_coral_wall_fan|shulker_box|amethyst_bud|_tulip"
    r"|_mushroom|_roots|_fungus|_petals|_bush|eyeblossom)$"
    r"|^minecraft:(dandelion|poppy|blue_orchid|allium|azure_bluet|oxeye_daisy|cornflower"
    r"|lily_of_the_valley|wither_rose|torchflower|sunflower|lilac|rose_bush|peony"
    r"|pitcher_plant|wildflowers|leaf_litter|short_dry_grass|tall_dry_grass|firefly_bush)$"
)
_PUSH_ONLY = re.compile(r"_glazed_terracotta$")
_STICKY = frozenset({"minecraft:slime_block", "minecraft:honey_block"})
_PISTONS = frozenset({"minecraft:piston", "minecraft:sticky_piston"})


def reaction(s: BlockState) -> str:
    """``"air"``, ``"normal"``, ``"destroy"``, ``"block"`` (immovable) or ``"push_only"``."""
    n = s.name
    if s.is_air:
        return "air"
    if n in _FLUIDS or n in _DESTROY_EXACT or _DESTROY_PATTERNS.search(n):
        return "destroy"
    if n in _PISTONS:
        return "block" if s.get("extended") == "true" else "normal"
    if n in IMMOVABLE or _IMMOVABLE_PATTERNS.search(n) or slots_for(n) is not None:
        return "block"
    if _PUSH_ONLY.search(n):
        return "push_only"
    return "normal"


def is_sticky(s: BlockState) -> bool:
    """Slime or honey block."""
    return s.name in _STICKY


def _stick(a: BlockState, b: BlockState) -> bool:
    if {a.name, b.name} == _STICKY:
        return False
    return is_sticky(a) or is_sticky(b)


def _pushable(s: BlockState, move: Dir, allow_destroy: bool, piston_facing: Dir) -> bool:
    r = reaction(s)
    if r == "air":
        return True
    if r == "block":
        return False
    if r == "destroy":
        return allow_destroy
    if r == "push_only":
        return move == piston_facing
    return True


@dataclass
class Movement:
    """Result of resolving a push or pull."""

    ok: bool
    direction: Dir
    to_push: list[Vec3] = field(default_factory=list)
    to_destroy: list[Vec3] = field(default_factory=list)
    reason: str = ""


def resolve(
    get: Callable[[Vec3], BlockState], piston: Vec3, facing: Dir, extending: bool
) -> Movement:
    """Blocks moved by the piston at ``piston`` (``PistonStructureResolver.resolve``)."""
    move = facing if extending else facing.opposite
    start = step(piston, facing) if extending else step(piston, facing, 2)
    res = Movement(True, move)
    to_push = res.to_push

    def fail(why: str) -> bool:
        res.reason = res.reason or why
        return False

    def add_line(origin: Vec3, line_dir: Dir) -> bool:
        s = get(origin)
        if s.is_air or origin == piston or origin in to_push:
            return True
        if not _pushable(s, move, False, line_dir):
            return True
        n = 1
        if n + len(to_push) > PUSH_LIMIT:
            return fail(f"more than {PUSH_LIMIT} blocks")
        while is_sticky(s):
            behind = step(origin, move.opposite, n)
            prev, s = s, get(behind)
            if (
                s.is_air
                or not _stick(prev, s)
                or not _pushable(s, move, False, move.opposite)
                or behind == piston
            ):
                break
            n += 1
            if n + len(to_push) > PUSH_LIMIT:
                return fail(f"more than {PUSH_LIMIT} blocks")
        added = 0
        for j in range(n - 1, -1, -1):
            to_push.append(step(origin, move.opposite, j))
            added += 1
        k = 1
        while True:
            ahead = step(origin, move, k)
            if ahead in to_push:
                idx = to_push.index(ahead)
                _reorder(to_push, added, idx)
                for q in list(to_push[: idx + added + 1]):
                    if is_sticky(get(q)) and not add_branches(q):
                        return False
                return True
            s = get(ahead)
            if s.is_air:
                return True
            if ahead == piston or not _pushable(s, move, True, move):
                return fail(f"{s.short_name} at {ahead} cannot move")
            if reaction(s) == "destroy":
                res.to_destroy.append(ahead)
                return True
            if len(to_push) >= PUSH_LIMIT:
                return fail(f"more than {PUSH_LIMIT} blocks")
            to_push.append(ahead)
            added += 1
            k += 1

    def add_branches(origin: Vec3) -> bool:
        s = get(origin)
        for d in ALL:
            if d in (move, move.opposite):
                continue
            q = step(origin, d)
            if _stick(get(q), s) and not add_line(q, d):
                return False
        return True

    first = get(start)
    if not _pushable(first, move, False, facing):
        if extending and reaction(first) == "destroy":
            res.to_destroy.append(start)
            return res
        res.ok = False
        res.reason = f"{first.short_name} at {start} cannot move"
        return res
    if not add_line(start, move):
        res.ok = False
        return res
    i = 0
    while i < len(to_push):
        q = to_push[i]
        if is_sticky(get(q)) and not add_branches(q):
            res.ok = False
            return res
        i += 1
    return res


def _reorder(to_push: list[Vec3], offset: int, index: int) -> None:
    """``PistonStructureResolver.reorderListAtCollision``."""
    head = to_push[:index]
    tail = to_push[len(to_push) - offset :]
    middle = to_push[index : len(to_push) - offset]
    to_push[:] = head + tail + middle


__all__ = ["PUSH_LIMIT", "Movement", "is_sticky", "reaction", "resolve"]
