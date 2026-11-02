"""Block → block-entity type table and the id filling in the writers (issue #39)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from schemsmith.core import Region, Structure
from schemsmith.core.block_entities import (
    EXACT,
    block_entity_id,
    comparator_signals,
    filled_ids_note,
    missing_ids,
    with_block_entity_id,
)
from schemsmith.formats import encode_structure, load_structure, save_structure
from schemsmith.nbt import Byte, Compound, Int, List, String, TagType
from schemsmith.registry import load_registry

REGISTRIES = ("1.21.11", "26.3")

# Every block-entity type of the game (BlockEntityType registry, 26.3).
TYPES = {
    "furnace", "chest", "trapped_chest", "ender_chest", "jukebox", "dispenser", "dropper",
    "sign", "hanging_sign", "mob_spawner", "creaking_heart", "piston", "brewing_stand",
    "enchanting_table", "end_portal", "beacon", "skull", "daylight_detector", "hopper",
    "comparator", "banner", "structure_block", "end_gateway", "command_block", "shulker_box",
    "bed", "conduit", "barrel", "smoker", "blast_furnace", "lectern", "bell", "jigsaw",
    "campfire", "beehive", "sculk_sensor", "calibrated_sculk_sensor", "sculk_catalyst",
    "sculk_shrieker", "chiseled_bookshelf", "shelf", "brushable_block", "decorated_pot",
    "crafter", "trial_spawner", "vault", "test_block", "test_instance_block",
    "copper_golem_statue",
}  # fmt: skip

# Names that look like a block-entity block but are not one.
LOOKALIKES = {
    "piston", "sticky_piston", "piston_head", "bookshelf", "flower_pot", "end_portal_frame",
    "nether_portal", "sculk", "sculk_vein", "shelf_mushroom", "structure_void",
    "potatoes", "potent_sulfur",
}  # fmt: skip
KEYWORDS = re.compile(
    r"chest|sign|banner|_head$|skull|_bed$|shulker|campfire|shelf|command|statue|furnace|"
    r"smoker|hopper|dropper|dispenser|jukebox|spawner|piston|brewing|enchant|portal|gateway|"
    r"beacon|daylight|comparator|structure|jigsaw|conduit|barrel|lectern|bell$|nest|beehive|"
    r"sculk|suspicious|pot$|crafter|vault|test|creaking"
)


@pytest.mark.parametrize("version", REGISTRIES)
def test_every_block_entity_block_in_the_registry_maps(version: str) -> None:
    names = [n.removeprefix("minecraft:") for n in load_registry(version).blocks]
    unmapped = [
        n for n in names if KEYWORDS.search(n) and n not in LOOKALIKES and not block_entity_id(n)
    ]
    assert unmapped == []
    assert not [n for n in LOOKALIKES if block_entity_id(n)]


def test_every_type_has_a_block_and_every_entry_is_a_real_block() -> None:
    names = set()
    for version in REGISTRIES:
        names |= {n.removeprefix("minecraft:") for n in load_registry(version).blocks}
    mapped = {block_entity_id(n) for n in names} - {None}
    assert mapped == {f"minecraft:{t}" for t in TYPES}
    assert sorted(set(EXACT) - names) == []


@pytest.mark.parametrize(
    ("block", "expected"),
    [
        ("minecraft:chest[facing=north,type=single,waterlogged=false]", "minecraft:chest"),
        ("minecraft:trapped_chest", "minecraft:trapped_chest"),
        ("minecraft:lime_shulker_box", "minecraft:shulker_box"),
        ("minecraft:shulker_box", "minecraft:shulker_box"),
        ("minecraft:oak_wall_sign", "minecraft:sign"),
        ("minecraft:bamboo_hanging_sign", "minecraft:hanging_sign"),
        ("minecraft:mangrove_wall_hanging_sign", "minecraft:hanging_sign"),
        ("minecraft:red_bed[part=head]", "minecraft:bed"),
        ("minecraft:white_wall_banner", "minecraft:banner"),
        ("minecraft:creeper_wall_head", "minecraft:skull"),
        ("minecraft:wither_skeleton_skull", "minecraft:skull"),
        ("minecraft:spawner", "minecraft:mob_spawner"),
        ("minecraft:moving_piston", "minecraft:piston"),
        ("minecraft:soul_campfire", "minecraft:campfire"),
        ("minecraft:bee_nest", "minecraft:beehive"),
        ("minecraft:suspicious_gravel", "minecraft:brushable_block"),
        ("minecraft:waxed_oxidized_copper_chest", "minecraft:chest"),
        ("minecraft:repeating_command_block", "minecraft:command_block"),
        ("hopper", "minecraft:hopper"),
        ("minecraft:stone", None),
        ("minecraft:air", None),
        ("minecraft:piston_head", None),
        ("create:chest", None),
    ],
)
def test_block_entity_id(block: str, expected: str | None) -> None:
    assert block_entity_id(block) == expected


def test_existing_id_is_never_overwritten() -> None:
    nbt = Compound({"id": String("minecraft:something_else"), "Items": List(TagType.COMPOUND, [])})
    assert with_block_entity_id(nbt, "minecraft:chest") is nbt
    bare = Compound({"Items": List(TagType.COMPOUND, [])})
    filled = with_block_entity_id(bare, "minecraft:chest")
    assert filled.get_str("id") == "minecraft:chest" and "id" not in bare  # copy, input kept
    assert with_block_entity_id(bare, "minecraft:stone") is bare


# round trip: a Litematica chest without id, holding a 1.20.1 shulker item -----------------


def old_shulker_item() -> Compound:
    """A 1.20.1 shulker box item (fixture shape from the owner's farm, #39)."""
    inner = Compound({"Slot": Byte(0), "Count": Byte(64), "id": String("minecraft:bone_meal")})
    tag = Compound(
        {
            "display": Compound({"Lore": List(TagType.STRING, [String('"(+NBT)"')])}),
            "BlockEntityTag": Compound(
                {
                    "id": String("minecraft:shulker_box"),
                    "Items": List(TagType.COMPOUND, [inner]),
                }
            ),
        }
    )
    return Compound(
        {"Slot": Byte(0), "id": String("minecraft:shulker_box"), "Count": Byte(1), "tag": tag}
    )


def litematica_farm() -> Structure:
    r = Region((4, 2, 4))
    r.set_block(1, 0, 1, "minecraft:chest[facing=north,type=single,waterlogged=false]")
    r.block_entities[(1, 0, 1)] = Compound({"Items": List(TagType.COMPOUND, [old_shulker_item()])})
    r.set_block(2, 0, 1, "minecraft:oak_sign[rotation=0,waterlogged=false]")
    r.block_entities[(2, 0, 1)] = Compound({"id": String("minecraft:sign"), "is_waxed": Byte(0)})
    return Structure(regions=[r], data_version=3465, format="litematic")


@pytest.mark.parametrize("ext", [".nbt", ".schem"])
def test_litematic_to_game_formats_fills_the_chest_id(tmp_path: Path, ext: str) -> None:
    src = tmp_path / "farm.litematic"
    save_structure(litematica_farm(), src)
    s = load_structure(src)
    assert "id" not in s.regions[0].block_entities[(1, 0, 1)]  # Litematica stores none
    report = save_structure(s, tmp_path / f"farm{ext}")
    assert any("added the missing id to 1 block entity" in n for n in report.notes)
    back = load_structure(tmp_path / f"farm{ext}").regions[0].block_entities
    chest = back[(1, 0, 1)]
    assert chest.get_str("id") == "minecraft:chest"
    item = chest.get_list("Items")[0]
    assert isinstance(item, Compound)
    assert item == old_shulker_item()  # the items themselves are not touched
    assert back[(2, 0, 1)].get_str("id") == "minecraft:sign"
    assert "id" not in s.regions[0].block_entities[(1, 0, 1)]  # the input is not modified


def test_litematic_output_is_left_as_is() -> None:
    _, report = encode_structure(litematica_farm(), "litematic")
    assert not any("missing id" in n for n in report.notes)


def test_missing_ids_and_note() -> None:
    s = litematica_farm()
    s.regions[0].block_entities[(0, 1, 0)] = Compound({"Items": List(TagType.COMPOUND, [])})  # air
    assert [(f.pos, f.block_entity_id) for f in missing_ids(s.regions[0])] == [
        ((1, 0, 1), "minecraft:chest")
    ]
    assert filled_ids_note(s).startswith("added the missing id to 1 block entity")
    assert filled_ids_note(Structure(regions=[Region((1, 1, 1))])) == ""


# comparators without OutputSignal (#38, measured in the game) ---------------------------------


def comparator_row() -> Structure:
    """Comparators as litemapy saves them: block states only, no block entities.

    (1,0,0) powered, feeding wire of power 9; (1,0,2) powered, feeding a block;
    (1,0,4) unpowered; (1,0,6) powered with a block entity that already has a signal.
    """
    r = Region((3, 1, 7))
    r.set_block(1, 0, 0, "minecraft:comparator[facing=east,mode=compare,powered=true]")
    r.set_block(
        0, 0, 0, "minecraft:redstone_wire[east=side,north=none,power=9,south=none,west=none]"
    )
    r.set_block(1, 0, 2, "minecraft:comparator[facing=east,mode=compare,powered=true]")
    r.set_block(0, 0, 2, "minecraft:stone")
    r.set_block(1, 0, 4, "minecraft:comparator[facing=east,mode=subtract,powered=false]")
    r.set_block(1, 0, 6, "minecraft:comparator[facing=east,mode=compare,powered=true]")
    r.block_entities[(1, 0, 6)] = Compound(
        {"id": String("minecraft:comparator"), "OutputSignal": Int(4)}
    )
    return Structure(regions=[r], data_version=4671, format="litematic")


def test_comparator_signals() -> None:
    got = dict(comparator_signals(comparator_row().regions[0]))
    assert got == {(1, 0, 0): 9, (1, 0, 2): 15, (1, 0, 4): 0}  # (1,0,6) keeps its own


@pytest.mark.parametrize("ext", [".nbt", ".schem"])
def test_writers_add_comparator_output_signal(tmp_path: Path, ext: str) -> None:
    """A powered comparator without a block entity output 0 after /place in 26.3: the
    timer's torch fired a 2 gt pulse and started a round by itself (#38)."""
    s = comparator_row()
    report = save_structure(s, tmp_path / f"row{ext}")
    assert any("OutputSignal of 3 comparators" in n for n in report.notes)
    back = load_structure(tmp_path / f"row{ext}").regions[0].block_entities
    assert {p: (be.get_str("id"), be["OutputSignal"]) for p, be in back.items()} == {
        (1, 0, 0): ("minecraft:comparator", Int(9)),
        (1, 0, 2): ("minecraft:comparator", Int(15)),
        (1, 0, 4): ("minecraft:comparator", Int(0)),
        (1, 0, 6): ("minecraft:comparator", Int(4)),
    }
    assert s.regions[0].block_entities.keys() == {(1, 0, 6)}  # the input is not modified
