"""Which block holds which block entity (block-entity type ids).

The game picks a block entity's data fixer by its ``id``. Litematica stores
block entities without ``id`` (``{Items: [...]}`` only), and a 1.20.1 chest
written that way into a ``.nbt`` template kept its old-format items un-upgraded:
26.3 placed the shulker boxes inside it empty (issue #39, measured in the game).
The writers for the formats the game reads (``.nbt``, ``.schem``) therefore add
a missing ``id`` derived from the block with :func:`block_entity_id`; an
existing ``id`` is never replaced.

The block registry (``registry/data``) has no block-entity data, so this is a
hand-written table, checked by ``tests/core/test_block_entities.py`` against
every block of every bundled registry. Types follow the game's
``BlockEntityType`` registry: several blocks can share one type (every sign is
``minecraft:sign``, every shulker box ``minecraft:shulker_box``), and
``chest`` and ``trapped_chest`` stay separate.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from schemsmith.nbt import Compound, String

if TYPE_CHECKING:  # structure.py imports this module (Region.prune_block_entities)
    from schemsmith.core.structure import Region, Structure

Vec3 = tuple[int, int, int]
ORPHAN_RULE = "orphan-block-entity"
MAX_LISTED = 5

_COLORS = (
    "white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray",
    "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black",
)  # fmt: skip
_COPPER = ("", "exposed_", "weathered_", "oxidized_")

EXACT: dict[str, str] = {
    # block (without namespace) -> block-entity type (without namespace)
    "furnace": "furnace",
    "smoker": "smoker",
    "blast_furnace": "blast_furnace",
    "chest": "chest",
    "trapped_chest": "trapped_chest",
    "ender_chest": "ender_chest",
    "jukebox": "jukebox",
    "dispenser": "dispenser",
    "dropper": "dropper",
    "spawner": "mob_spawner",
    "creaking_heart": "creaking_heart",
    "moving_piston": "piston",
    "brewing_stand": "brewing_stand",
    "enchanting_table": "enchanting_table",
    "end_portal": "end_portal",
    "end_gateway": "end_gateway",
    "beacon": "beacon",
    "daylight_detector": "daylight_detector",
    "hopper": "hopper",
    "comparator": "comparator",
    "structure_block": "structure_block",
    "jigsaw": "jigsaw",
    "command_block": "command_block",
    "chain_command_block": "command_block",
    "repeating_command_block": "command_block",
    "shulker_box": "shulker_box",
    "conduit": "conduit",
    "barrel": "barrel",
    "lectern": "lectern",
    "bell": "bell",
    "campfire": "campfire",
    "soul_campfire": "campfire",
    "bee_nest": "beehive",
    "beehive": "beehive",
    "sculk_sensor": "sculk_sensor",
    "calibrated_sculk_sensor": "calibrated_sculk_sensor",
    "sculk_catalyst": "sculk_catalyst",
    "sculk_shrieker": "sculk_shrieker",
    "chiseled_bookshelf": "chiseled_bookshelf",
    "suspicious_sand": "brushable_block",
    "suspicious_gravel": "brushable_block",
    "decorated_pot": "decorated_pot",
    "crafter": "crafter",
    "trial_spawner": "trial_spawner",
    "vault": "vault",
    "test_block": "test_block",
    "test_instance_block": "test_instance_block",
    "skeleton_skull": "skull",
    "skeleton_wall_skull": "skull",
    "wither_skeleton_skull": "skull",
    "wither_skeleton_wall_skull": "skull",
}
for _c in _COLORS:
    EXACT[f"{_c}_shulker_box"] = "shulker_box"
    EXACT[f"{_c}_bed"] = "bed"
    EXACT[f"{_c}_banner"] = "banner"
    EXACT[f"{_c}_wall_banner"] = "banner"
for _w in ("", "waxed_"):
    for _o in _COPPER:
        EXACT[f"{_w}{_o}copper_chest"] = "chest"  # copper chests are chests (1.21.9)
        EXACT[f"{_w}{_o}copper_golem_statue"] = "copper_golem_statue"

SUFFIXES: tuple[tuple[str, str], ...] = (
    # checked in order, after EXACT; covers every wood type, old and future
    ("_wall_hanging_sign", "hanging_sign"),
    ("_hanging_sign", "hanging_sign"),
    ("_wall_sign", "sign"),
    ("_sign", "sign"),
    ("_wall_head", "skull"),
    ("_head", "skull"),
    ("_bed", "bed"),
    ("_shelf", "shelf"),
)
NOT_BLOCK_ENTITIES = frozenset({"piston_head", "shelf_mushroom"})
"""Names that end like a block-entity block but are not one."""


def block_entity_id(block: str) -> str | None:
    """The block-entity type id for a block name (``minecraft:chest`` → ``minecraft:chest``).

    ``None`` when the block holds no block entity, or is not a vanilla block.
    Block-state properties (``[facing=north]``) are ignored.
    """
    name = block.split("[", 1)[0]
    ns, _, path = name.rpartition(":")
    if ns not in ("", "minecraft") or path in NOT_BLOCK_ENTITIES:
        return None
    be = EXACT.get(path)
    if be is None:
        be = next((t for suffix, t in SUFFIXES if path.endswith(suffix)), None)
    return f"minecraft:{be}" if be else None


def is_vanilla(block: str) -> bool:
    """True for ``minecraft:`` (or un-namespaced) block names."""
    return block.split("[", 1)[0].rpartition(":")[0] in ("", "minecraft")


def holds_block_entity(block: str) -> bool | None:
    """True when the block holds a block entity, False when a vanilla block cannot,
    None for a block schemsmith does not know (a mod's): never treated as an orphan."""
    if block_entity_id(block) is not None:
        return True
    return False if is_vanilla(block) else None


def orphans_in(region: Region) -> Iterator[tuple[Vec3, str]]:
    """``(local pos, block)`` of block entities whose block cannot hold one.

    A position outside the region counts too (its block is reported as ``""``).
    """
    for pos in sorted(region.block_entities):
        if not region.contains(*pos):
            yield pos, ""
            continue
        block = region.get_block(*pos).name
        if holds_block_entity(block) is False:
            yield pos, block


@dataclass(frozen=True)
class Orphan:
    """A block entity left at a block that cannot hold one (structure coordinates)."""

    pos: Vec3
    block: str
    block_entity_id: str
    """Its own ``id``, or ``""`` when it has none."""


def find_orphan_block_entities(structure: Structure) -> list[Orphan]:
    """Every orphan block entity of the structure."""
    out: list[Orphan] = []
    for region in structure.regions:
        mc = region.min_corner
        for (x, y, z), block in orphans_in(region):
            v = region.block_entities[(x, y, z)].get("id")
            out.append(
                Orphan(
                    (mc[0] + x, mc[1] + y, mc[2] + z),
                    block or "outside the region",
                    v.value if isinstance(v, String) else "",
                )
            )
    return out


ORPHAN_HINT = (
    "Region.set_block keeps the block entity of the block it replaces; drop the leftovers "
    "with Region.prune_block_entities() (Python) or put the container back"
)


def orphan_warning(orphans: list[Orphan]) -> str:
    """The ``orphan-block-entity`` message ('' if none)."""
    if not orphans:
        return ""
    listed = ", ".join(
        f"({o.pos[0]},{o.pos[1]},{o.pos[2]}) {o.block.removeprefix('minecraft:')}"
        for o in orphans[:MAX_LISTED]
    )
    if len(orphans) > MAX_LISTED:
        listed += f" and {len(orphans) - MAX_LISTED} more"
    noun = "block entity" if len(orphans) == 1 else "block entities"
    return (
        f"{len(orphans)} {noun} at blocks that cannot hold one: {listed}; the game ignores "
        "them, but their old contents still show up in tools that read the file"
    )


def with_block_entity_id(nbt: Compound, block: str) -> Compound:
    """``nbt`` itself when it has an ``id`` (or none can be inferred), else a copy with one."""
    if "id" in nbt:
        return nbt
    be = block_entity_id(block)
    if be is None:
        return nbt
    out = Compound(nbt)
    out["id"] = String(be)
    return out


@dataclass(frozen=True)
class FilledId:
    """One block entity that got its ``id`` from the block."""

    pos: Vec3
    block: str
    block_entity_id: str


def missing_ids(region: Region) -> Iterator[FilledId]:
    """Block entities without ``id`` whose block tells the type (local coordinates)."""
    for pos, nbt in sorted(region.block_entities.items()):
        if "id" in nbt or not region.contains(*pos):
            continue
        block = region.get_block(*pos).name
        be = block_entity_id(block)
        if be is not None:
            yield FilledId(pos, block, be)


def filled_ids_note(structure: Structure) -> str:
    """The writer note for :func:`missing_ids` over all regions ('' if none)."""
    n = sum(1 for r in structure.regions for _ in missing_ids(r))
    if not n:
        return ""
    noun = "block entity" if n == 1 else "block entities"
    return f"added the missing id to {n} {noun} from the block, so the game can upgrade them (#39)"


__all__ = [
    "EXACT",
    "NOT_BLOCK_ENTITIES",
    "ORPHAN_HINT",
    "ORPHAN_RULE",
    "SUFFIXES",
    "FilledId",
    "Orphan",
    "block_entity_id",
    "filled_ids_note",
    "find_orphan_block_entities",
    "holds_block_entity",
    "is_vanilla",
    "missing_ids",
    "orphan_warning",
    "orphans_in",
    "with_block_entity_id",
]
