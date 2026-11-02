"""Block entities left behind at positions whose block cannot hold one."""

from __future__ import annotations

from schemsmith.core import Region, Structure
from schemsmith.core.block_entities import (
    ORPHAN_RULE,
    find_orphan_block_entities,
    holds_block_entity,
    orphan_warning,
)
from schemsmith.core.old_items import find_old_container_items
from schemsmith.nbt import Byte, Compound, List, String, TagType
from schemsmith.registry import load_registry, validate_structure

CHEST = "minecraft:chest[facing=north,type=single,waterlogged=false]"


def old_shulker() -> Compound:
    inner = Compound({"Slot": Byte(0), "Count": Byte(64), "id": String("minecraft:bone_meal")})
    tag = Compound({"BlockEntityTag": Compound({"Items": List(TagType.COMPOUND, [inner])})})
    return Compound(
        {"Slot": Byte(0), "id": String("minecraft:shulker_box"), "Count": Byte(1), "tag": tag}
    )


def farm_edited_to_air() -> Region:
    """The owner's case: chests replaced with air by ``set_block`` keep their contents."""
    r = Region((4, 2, 4))
    for x in (0, 1, 2):
        r.set_block(x, 0, 0, CHEST)
        r.block_entities[(x, 0, 0)] = Compound({"Items": List(TagType.COMPOUND, [old_shulker()])})
    r.set_block(0, 0, 0, "minecraft:air")  # documented: the block entity stays
    r.set_block(1, 0, 0, "minecraft:stone")
    r.block_entities[(3, 1, 3)] = Compound({"id": String("minecraft:sign")})  # air, with id
    r.block_entities[(3, 0, 3)] = Compound({"id": String("mymod:thing")})
    r.set_block(3, 0, 3, "mymod:machine")  # unknown block: kept
    return r


def test_holds_block_entity() -> None:
    assert holds_block_entity("minecraft:chest") is True
    assert holds_block_entity("minecraft:air") is False
    assert holds_block_entity("minecraft:stone") is False
    assert holds_block_entity("mymod:machine") is None  # unknown, never pruned


def test_set_block_keeps_the_block_entity() -> None:
    r = farm_edited_to_air()
    assert (0, 0, 0) in r.block_entities


def test_prune_drops_orphans_and_returns_them() -> None:
    r = farm_edited_to_air()
    removed = r.prune_block_entities()
    assert sorted(removed) == [(0, 0, 0), (1, 0, 0), (3, 1, 3)]
    assert sorted(r.block_entities) == [(2, 0, 0), (3, 0, 3)]
    assert r.prune_block_entities() == {}


def test_prune_drops_block_entities_outside_the_region() -> None:
    r = Region((1, 1, 1))
    r.block_entities[(5, 5, 5)] = Compound()
    assert list(r.prune_block_entities()) == [(5, 5, 5)]


def test_find_and_warn() -> None:
    s = Structure(regions=[farm_edited_to_air()])
    found = find_orphan_block_entities(s)
    assert [(o.pos, o.block) for o in found] == [
        ((0, 0, 0), "minecraft:air"),
        ((1, 0, 0), "minecraft:stone"),
        ((3, 1, 3), "minecraft:air"),
    ]
    msg = orphan_warning(found)
    assert msg.startswith(
        "3 block entities at blocks that cannot hold one: (0,0,0) air, (1,0,0) stone"
    )
    assert orphan_warning([]) == ""


def test_old_items_detector_ignores_orphans() -> None:
    assert find_old_container_items(Structure(regions=[farm_edited_to_air()])) == []


def test_validate_warns_with_fix_hint() -> None:
    r = farm_edited_to_air()
    r.set_block(3, 0, 3, "minecraft:stone")
    del r.block_entities[(3, 0, 3)]
    diags = validate_structure(Structure(regions=[r]), load_registry("26.3"))
    orphans = [d for d in diags if d.rule_id == ORPHAN_RULE]
    assert len(orphans) == 1 and orphans[0].severity == "warning"
    assert orphans[0].pos == (0, 0, 0)
    assert orphans[0].suggestion is not None and "prune_block_entities()" in orphans[0].suggestion
    assert ORPHAN_RULE == "orphan-block-entity"
