"""Material lists."""

from __future__ import annotations

from pathlib import Path

import pytest

from schemsmith.core import BlockState, Region, Structure
from schemsmith.formats import load_structure
from schemsmith.guide import item_for, material_list
from schemsmith.guide.materials import MaterialLine, format_stacks
from schemsmith.library import get_module
from schemsmith.redstone.sim import load_script

FIX = Path(__file__).resolve().parents[2] / "fixtures"

TIMER_V3 = {
    "minecraft:stone": 165,
    "minecraft:redstone": 12,
    "minecraft:polished_andesite": 7,
    "minecraft:repeater": 6,
    "minecraft:comparator": 4,
    "minecraft:hopper": 4,
    "minecraft:redstone_torch": 3,
    "minecraft:stone_button": 2,
    "minecraft:bell": 1,
    "minecraft:dispenser": 1,
    "minecraft:dropper": 1,
    "minecraft:jukebox": 1,
    "minecraft:redstone_lamp": 1,
    "minecraft:waxed_copper_bulb": 1,
}


def test_timer_v3_exact() -> None:
    m = material_list(load_structure_v3())
    assert {line.item: line.count for line in m.lines} == TIMER_V3
    assert m.total_items == 209
    assert m.total_stacks == 3 + 13  # stone needs 3 slots, 13 other items 1 slot each
    assert m.shulker_boxes == 1
    assert m.contents == []


def load_structure_v3() -> Structure:
    return load_structure(FIX / "timer_v3_fixed.litematic")


def test_script_contents_listed_separately() -> None:
    m = material_list(load_structure_v3(), load_script(FIX / "timer_start.yaml"))
    assert {line.item: line.count for line in m.lines} == TIMER_V3
    hopper_a = next(c for c in m.contents if c.pos == (4, 1, 7))
    assert hopper_a.items == [("minecraft:cobblestone", 188)] and hopper_a.source == "script"
    assert m.to_dict()["container_contents"][0]["items"][0]["count"] == 188


def test_block_entity_contents_from_schematic() -> None:
    region = get_module("game_timer").build()
    m = material_list(Structure(regions=[region], data_version=4671))
    by_pos = {c.pos: c for c in m.contents}
    assert by_pos[(4, 1, 7)].items[0][1] + sum(n for _, n in by_pos[(4, 1, 7)].items[1:]) == 188
    assert by_pos[(12, 1, 1)].items == [("minecraft:music_disc_pigstep", 1)]


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("redstone_wire", ("minecraft:redstone", 1)),
        ("oak_door[half=upper]", None),
        ("oak_door[half=lower]", ("minecraft:oak_door", 1)),
        ("red_bed[part=head]", None),
        ("stone_slab[type=double]", ("minecraft:stone_slab", 2)),
        ("oak_wall_sign[facing=north]", ("minecraft:oak_sign", 1)),
        ("water[level=0]", ("minecraft:water_bucket", 1)),
        ("water[level=3]", None),
        ("candle[candles=3,lit=false]", ("minecraft:candle", 3)),
        ("piston_head[facing=north]", None),
        ("air", None),
        ("pumpkin_stem[age=0]", ("minecraft:pumpkin_seeds", 1)),
        ("player_wall_head[facing=north]", ("minecraft:player_head", 1)),
        ("white_wall_banner[facing=north]", ("minecraft:white_banner", 1)),
        ("oak_wall_hanging_sign[facing=north]", ("minecraft:oak_hanging_sign", 1)),
    ],
)
def test_item_for(state: str, expected: tuple[str, int] | None) -> None:
    assert item_for(BlockState.parse(state)) == expected


def test_stacks_formatting() -> None:
    assert format_stacks(MaterialLine("minecraft:stone", 165)) == "2 stacks + 37"
    assert format_stacks(MaterialLine("minecraft:stone", 64)) == "1 stack"
    assert format_stacks(MaterialLine("minecraft:snowball", 20)) == "1 stack + 4 (x16)"
    assert format_stacks(MaterialLine("minecraft:water_bucket", 3)) == "3"
    r = Region((30, 30, 30))
    for x in range(30):
        for y in range(30):
            for z in range(30):
                r.set_block(x, y, z, "stone")
    assert material_list(Structure(regions=[r])).shulker_boxes == 16  # 27000 items = 422 stacks
